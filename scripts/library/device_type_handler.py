"""
This script is a subcomponent of the main script - device_type_provisioning.py

Author: Kenneth Acar Garcia
Email: kenneth[.]acar[.]garcia[@]gmail[.]com
"""

import yaml
from dcim.models import DeviceType, Manufacturer, InterfaceTemplate, PowerPortTemplate, ConsolePortTemplate

class DeviceTypeHandler(object):
    '''
    Custom class to handle different types of operation for DeviceType object and its related objects
    '''
    def __init__(
        self,
        manufacturer: str, #DeviceType manufacturer from user uploaded yaml file
        part_number: str, #DeviceType model from user uploaded yaml file
        yaml_template: str = None, #Yaml template from NetBox devicetype-library
        devicetype_obj: DeviceType = None, #DeviceType object model for importing or updating
        manufacturer_obj: Manufacturer = None, #Manufacturer object model for importing or allocation
        update_existing_record: bool = False, #Allow updating existing record for any difference with devicetype library template
    ) -> None:
        
        self.manufacturer = manufacturer
        self.part_number = part_number
        if yaml_template:
            self.dict_template = yaml.safe_load(yaml_template)
        else:
            self.dict_template = yaml_template
        self.devicetype_obj = devicetype_obj
        self.manufacturer_obj = manufacturer_obj
        self.imported_interfacetemplates: list[str] = [] #Placeholder of imported InterfaceTemplate object list
        self.updated_interfacetemplates: list[str] = [] #Placeholder of updated InterfaceTemplate object list
        self.deleted_interfacetemplates: list[str] = [] #Placeholder of deleted InterfaceTemplate object list
        self.imported_powerporttemplates: list[str] = [] #Placeholder of imported PowerPortTemplate object list
        self.updated_powerporttemplates: list[str] = [] #Placeholder of updated PowerPortTemplate object list
        self.deleted_powerporttemplates: list[str] = [] #Placeholder of deleted PowerPortTemplate object list
        self.imported_consoleporttemplates: list[str] = [] #Placeholder of imported ConsolePortTemplate object list
        self.updated_consoleporttemplates: list[str] = [] #Placeholder of updated ConsolePortTemplate object list
        self.deleted_consoleporttemplates: list[str] = [] #Placeholder of deleted ConsolePortTemplate object list
        self.update_existing_record = update_existing_record #Placeholder of user option in updating existing records
        self.operation_mode: bool = None #Placeholder of operation mode triggered for this object. True if import and False if update
    
    def _search_device_type(self) -> bool:
        '''
        Private method to search the part_number in existing DeviceType records.
        Returns True if part_number is found and False if not.
        '''
        try:
            DeviceType.objects.get(part_number=self.part_number)
            return True
        except DeviceType.DoesNotExist:
            return False

    def _search_manufacturer(self) -> bool:
        '''
        Private method to search the vendor in existing Manufacturer records.
        Returns True if vendor is found and False if not.
        '''
        try:
            Manufacturer.objects.get(name=self.manufacturer)
            return True
        except Manufacturer.DoesNotExist:
            return False
    
    def _import_manufacturer(self) -> None:
        '''
        Private method to import Manufacture object if vendor not found in existing records.
        '''
        self.manufacturer_obj = Manufacturer(
            name = self.manufacturer
        )
        self.manufacturer_obj.save()

    def _delete_interface_template(self, interfacetemplates: list[InterfaceTemplate]) -> None:
        '''
        Private method to delete existing InterfaceTemplate object which is not matching rom the reference DeviceType library template.
        '''
        for_deleting_list = []
        queryable_template_list = [ interface['name'] for interface in self.dict_template['interfaces'] ]
        for interface in interfacetemplates:
            if interface.name not in queryable_template_list:
                for_deleting_list.append(interface)

        for interface in for_deleting_list:
            interface.delete()
            self.deleted_interfacetemplates.append(f"{interface.device_type.model}: {interface.name}")
       
    def _update_interface_template(self) -> None:
        '''
        Private method to update existing InterfaceTemplate object or import if missing from the reference DeviceType library template.
        '''
        #Fetch all related InterfaceTemplate objects to the matching DeviceType object.
        existing_obj_list = InterfaceTemplate.objects.filter(device_type=self.devicetype_obj)
        
        #Transform list of InterfaceTemplate objects into python dict format for easier comparison logic.
        existing_obj_list_to_dict = { obj.name: {'type': obj.type, 'mgmt_only': obj.mgmt_only} for obj in existing_obj_list }
        
        #Placeholder of existing InterfaceTemplate objects in dict format for updating.
        for_updating_list = []
        
        #Placeholder of InterfaceTemplate templates in dict format for importing.
        for_importing_list = []
        
        #Iterate the list of interfaces in devicetype-library template and match it to the existing list of InterfaceTemplate objects.
        for interface in self.dict_template['interfaces']:
            if interface['name'] in existing_obj_list_to_dict:
                diff_count = 0
                for param in ['type', 'mgmt_only']:
                    if param in interface:
                        if existing_obj_list_to_dict[interface['name']][param] != interface[param]:
                            diff_count += 1
                    else:
                        if existing_obj_list_to_dict[interface['name']][param]:
                            diff_count += 1
                if diff_count != 0:
                    for_updating_list.append(interface)
            else:
                for_importing_list.append(interface)
        
        #Iterate the placeholder of existing InterfaceTemplate objects list for record updating in database
        for interface in for_updating_list:
            existing_obj_to_update = InterfaceTemplate.objects.get(
                device_type = self.devicetype_obj,
                name = interface['name'],
            )
            
            existing_obj_to_update.type = interface['type']
            if 'mgmt_only' in interface:
                existing_obj_to_update.mgmt_only = interface['mgmt_only']
            else:
                existing_obj_to_update.mgmt_only = False
            existing_obj_to_update.save()
            self.updated_interfacetemplates.append(f"{existing_obj_to_update.device_type.model}: {existing_obj_to_update.name}")

        #Import any item in placeholder of existing InterfaceTemplate objects list using self._import_interface_template private method
        if for_importing_list != []:
            self._import_interface_template(
                interfaces_dict_list = for_importing_list,
                # devicetype_obj = self.devicetype_obj
            )

        #Trigger delete private method if total count is different between template interface list and latest interface record 
        template_count = len(self.dict_template['interfaces'])
        latest_interfacetemplates = InterfaceTemplate.objects.filter(device_type=self.devicetype_obj)
        existing_count = len(latest_interfacetemplates)
        if template_count != existing_count:
            self._delete_interface_template(latest_interfacetemplates)

    def _import_interface_template(
            self,
            interfaces_dict_list: dict,
    ) -> None:
        '''
        Private method to import InterfaceTemplate objects from the reference DeviceType library template.
        '''
        for_importing_list = []
        for interface in interfaces_dict_list:
        # for interface in self.dict_template['interfaces']:
            if 'mgmt_only' in interface:
                for_importing_list.append(
                    InterfaceTemplate(
                        device_type = self.devicetype_obj,
                        name = interface['name'],
                        type = interface['type'],
                        mgmt_only = interface['mgmt_only']
                    )
                )
            else:
                for_importing_list.append(
                    InterfaceTemplate(
                        device_type = self.devicetype_obj,
                        name = interface['name'],
                        type = interface['type'],
                    )
                )
        for interface in for_importing_list:
            interface.save()
            self.imported_interfacetemplates.append(f"{interface.device_type.model}: {interface.name}")

    def _delete_consoleport_template(self, consoleporttemplates: list[ConsolePortTemplate]) -> None:
        '''
        Private method to delete existing ConsolePortTemplate object which is not matching rom the reference DeviceType library template.
        '''
        for_deleting_list = []
        queryable_template_list = [ consoleport['name'] for consoleport in self.dict_template['console-ports'] ]
        for consoleport in consoleporttemplates:
            if consoleport.name not in queryable_template_list:
                for_deleting_list.append(consoleport)

        for consoleport in for_deleting_list:
            consoleport.delete()
            self.deleted_consoleporttemplates.append(f"{consoleport.device_type.model}: {consoleport.name}")

    def _update_consoleport_template(self) -> None:
        '''
        Private method to update existing ConsolePortTemplate object or import if missing from the reference DeviceType library template.
        '''
        #Fetch all related ConsolePortTemplate objects to the matching DeviceType object.
        existing_obj_list = ConsolePortTemplate.objects.filter(device_type=self.devicetype_obj)
        
        #Transform list of ConsolePortTemplate objects into python dict format for easier comparison logic.
        existing_obj_list_to_dict = { obj.name: { 'type': obj.type } for obj in existing_obj_list }
        
        #Placeholder of existing ConsolePortTemplate objects in dict format for updating.
        for_updating_list = []
        
        #Placeholder of ConsolePortTemplate templates in dict format for importing.
        for_importing_list = []
        
        #Iterate the list of console-ports in devicetype-library template and match it to the existing list of ConsolePortTemplate objects.
        for consoleport in self.dict_template['console-ports']:
            if consoleport['name'] in existing_obj_list_to_dict:                
                for param in ['type']:
                    if existing_obj_list_to_dict[consoleport['name']][param] != consoleport[param]:
                        for_updating_list.append(consoleport)
            else:
                for_importing_list.append(consoleport)
        
        #Iterate the placeholder of existing ConsolePortTemplate objects list for record updating in database
        for consoleport in for_updating_list:
            existing_obj_to_update = ConsolePortTemplate.objects.get(
                device_type = self.devicetype_obj,
                name = consoleport['name'],
            )
            
            existing_obj_to_update.type = consoleport['type']
            existing_obj_to_update.save()
            self.updated_consoleporttemplates.append(f"{existing_obj_to_update.device_type.model}: {existing_obj_to_update.name}")

        #Import any item in placeholder of existing ConsolePortTemplate objects list using self._import_consoleport_template private method
        if for_importing_list != []:
            self._import_consoleport_template(
                consoleports_dict_list = for_importing_list,
            )

        #Trigger delete private method if total count is different between template consoleport list and latest consoleport record 
        template_count = len(self.dict_template['console-ports'])
        latest_consoleporttemplates = ConsolePortTemplate.objects.filter(device_type=self.devicetype_obj)
        existing_count = len(latest_consoleporttemplates)
        if template_count != existing_count:
            self._delete_consoleport_template(latest_consoleporttemplates)

    def _import_consoleport_template(
            self,
            consoleports_dict_list: dict,
    ) -> None:
        '''
        Method to import ConsolePortTemplate objects from template
        '''
        for_importing_list = []
        for consoleport in consoleports_dict_list:
            for_importing_list.append(
                ConsolePortTemplate(
                    device_type = self.devicetype_obj,
                    name = consoleport['name'],
                    type = consoleport['type'],
                )
            )
        for consoleport in for_importing_list:
            consoleport.save()
            self.imported_consoleporttemplates.append(f"{consoleport.device_type.model}: {consoleport.name}")

    def _delete_powerport_template(self, powerporttemplates: list[PowerPortTemplate]) -> None:
        '''
        Private method to delete existing PowerPortTemplate object which is not matching rom the reference DeviceType library template.
        '''
        for_deleting_list = []
        queryable_template_list = [ powerport['name'] for powerport in self.dict_template['power-ports'] ]
        for powerport in powerporttemplates:
            if powerport.name not in queryable_template_list:
                for_deleting_list.append(powerport)

        for powerport in for_deleting_list:
            powerport.delete()
            self.deleted_powerporttemplates.append(f"{powerport.device_type.model}: {powerport.name}")

    def _update_powerport_template(self) -> None:
        '''
        Private method to update existing PowerPortTemplate object or import if missing from the reference DeviceType library template.
        '''
        #Fetch all related PowerPortTemplate objects to the matching DeviceType object.
        existing_obj_list = PowerPortTemplate.objects.filter(device_type=self.devicetype_obj)
        
        #Transform list of PowerPortTemplate objects into python dict format for easier comparison logic.
        existing_obj_list_to_dict = { obj.name: {
             'type': obj.type,
             'allocated_draw': obj.allocated_draw,
             'maximum_draw': obj.maximum_draw,
        } for obj in existing_obj_list }
        
        #Placeholder of existing PowerPortTemplate objects in dict format for updating.
        for_updating_list = []
        
        #Placeholder of PowerPortTemplate templates in dict format for importing.
        for_importing_list = []
        
        #Iterate the list of power-ports in devicetype-library template and match it to the existing list of PowerPortTemplate objects.
        for powerport in self.dict_template['power-ports']:
            if powerport['name'] in existing_obj_list_to_dict:                
                for param in ['type', 'allocated_draw', 'maximum_draw']:
                    if existing_obj_list_to_dict[powerport['name']][param] != powerport[param]:
                        for_updating_list.append(powerport)
            else:
                for_importing_list.append(powerport)
        
        #Iterate the placeholder of existing PowerPortTemplate objects list for record updating in database
        for powerport in for_updating_list:
            existing_obj_to_update = PowerPortTemplate.objects.get(
                device_type = self.devicetype_obj,
                name = powerport['name'],
            )
            
            existing_obj_to_update.type = powerport['type']
            existing_obj_to_update.allocated_draw = powerport['allocated_draw']
            existing_obj_to_update.maximum_draw = powerport['maximum_draw']
            existing_obj_to_update.save()
            self.updated_powerporttemplates.append(f"{existing_obj_to_update.device_type.model}: {existing_obj_to_update.name}")

        #Import any item in placeholder of existing PowerPortTemplate objects list using self._import_powerport_template private method
        if for_importing_list != []:
            self._import_powerport_template(
                powerports_dict_list = for_importing_list,
            )

        #Trigger delete private method if total count is different between template powerport list and latest powerport record 
        template_count = len(self.dict_template['power-ports'])
        latest_powerporttemplates = PowerPortTemplate.objects.filter(device_type=self.devicetype_obj)
        existing_count = len(latest_powerporttemplates)
        if template_count != existing_count:
            self._delete_powerport_template(latest_powerporttemplates)

    def _import_powerport_template(
            self,
            powerports_dict_list: dict,
    ) -> None:
        '''
        Private method to import PowerPortTemplate objects from template
        '''
        for_importing_list = []
        for powerport in powerports_dict_list:
            for_importing_list.append(
                PowerPortTemplate(
                    device_type = self.devicetype_obj,
                    name = powerport['name'],
                    type = powerport['type'],
                    allocated_draw = powerport['allocated_draw'],
                    maximum_draw = powerport['maximum_draw'],
                )
            )
        for powerport in for_importing_list:
            powerport.save()
            self.imported_powerporttemplates.append(f"{powerport.device_type.model}: {powerport.name}")

    def _update_record(self) -> None:
        '''
        Private method to update existing DeviceType object from the reference DeviceType library template.
        '''
        self.devicetype_obj = DeviceType.objects.get(part_number=self.part_number)
        existing_obj_dict = yaml.safe_load(self.devicetype_obj.to_yaml())
        params = [
            'manufacturer',
            'model',
            'slug',
            'u_height',
            'is_full_depth',
        ]
        for_updating_list = []
        for param in params:
            if existing_obj_dict[param] != self.dict_template[param]:
                for_updating_list.append(param)
        for param in for_updating_list:
            if param == 'manufacturer':
                self.devicetype_obj.manufacturer = Manufacturer.objects.get(name=self.manufacturer)
            elif param == 'model':
                self.devicetype_obj.model = self.dict_template[param]
            elif param == 'slug':
                self.devicetype_obj.slug = self.dict_template[param]
            elif param == 'u_height':
                self.devicetype_obj.u_height = self.dict_template[param]
            elif param == 'is_full_depth':
                self.devicetype_obj.is_full_depth = self.dict_template[param]
        if for_updating_list != []:
            self.devicetype_obj.save()
        self._update_interface_template()
        self._update_consoleport_template()
        self._update_powerport_template()
        self.operation_mode = False

    def import_record(self) -> DeviceType:
        '''
        Method to import DeviceType object from the reference DeviceType library template.
        '''
        if not self._search_device_type():
            if not self._search_manufacturer():
                self._import_manufacturer()
            else:
                self.manufacturer_obj = Manufacturer.objects.get(name=self.manufacturer)
            self.devicetype_obj = DeviceType(
                manufacturer = self.manufacturer_obj,
                model = self.dict_template['model'],
                part_number = self.part_number,
                slug = self.dict_template['slug'],
                u_height = self.dict_template['u_height'],
                is_full_depth = self.dict_template['is_full_depth'],
            )
            self.devicetype_obj.save()

            self._import_interface_template(
                interfaces_dict_list = self.dict_template['interfaces'],
            )

            self._import_consoleport_template(
                consoleports_dict_list = self.dict_template['console-ports'],
            )

            self._import_powerport_template(
                powerports_dict_list = self.dict_template['power-ports'],
            )
            self.operation_mode = True
        else:
            if self.update_existing_record:
                self._update_record()

    def __str__(self) -> str:
        return f"{self.manufacturer}: {self.part_number}"