"""
This script allows you to import or update exising devicetype record from Netbox's official devicetype-library git repository.
For more details and instruction, you may check this git repo: https://github.com/kagarcia1618/netbox_custom_script

Note: This scripts has dependency to two other folder found in the directory below:
- reports/scripts/library
- reports/scripts/template

Library folder contains the custom class script (device_type_handler.py) to compliment the main script (device_type_provisioning.py).
Template folder contains the jinja2 template file for generating the script report summary output.

Author: Kenneth Acar Garcia
Email: kenneth[.]acar[.]garcia[@]gmail[.]com
"""
import yaml
import requests
from jinja2 import Environment, FileSystemLoader
from extras.scripts import *
from dcim.models import DeviceType, Manufacturer, InterfaceTemplate, PowerPortTemplate, ConsolePortTemplate
from scripts.netbox_script.library.device_type_handler import DeviceTypeHandler

name = 'Import/Update DeviceType Provisioning Script'

class ImportDeviceType(Script):

    class Meta:
        name = "Import/Update Device Type"
        description = "Custom script to import or update local Netbox's Device Types from NetBox devicetype-library git repo"
        commit_default = False
        field_order = []

    yaml_data = FileVar(
        label = "Yaml File",
        description = '''Upload the yaml file with vendor and part number details using the format below:<br>---<br>- vendor: Cisco<br>&nbsp&nbsppart_numbers:<br>&nbsp&nbsp&nbsp&nbsp- N9K-C9332PQ<br>&nbsp&nbsp&nbsp&nbsp- N9K-C92348GC-X<br>- vendor: Arista<br>&nbsp&nbsppart_numbers:<br>&nbsp&nbsp&nbsp&nbsp- DCS-7010T-48'''
    )

    update_existing_record = BooleanVar(
        label = "Update Existing Record",
        description = "Toggle on to update existing device type records for any diff with devicetype-library record",
        default = False,
    )

    def run(self, data, commit):
        try:
            input_data = yaml.safe_load(data['yaml_data'].read().decode())
        except (yaml.scanner.ScannerError, yaml.parser.ParserError):
            self.log_failure("Please check the format of the uploaded yaml file.")
            return
        
        if not isinstance(input_data, list):
            self.log_failure("Please check the format of the uploaded yaml file.")
            return
        
        in_library_list = [] #Placeholder for user provided partnumber found in devicetype-library git repo
        not_in_library_list = [] #Placeholder for user provided partnumber not found in devicetype-library git repo
        imported_devicetype_list = [] #Placeholder for all imported devicetype from devicetype-library git repo
        updated_devicetype_list = [] #Placeholder for all updated existing devicetype from devicetype-library git repo
        up_to_date_devicetype_list = [] #Placeholder for all matched existing devicetype from devicetype-library git repo
        updated_interfacetemplate_list = [] #Placeholder for all updated interfacetemplates of existing devicetype
        deleted_interfacetemplate_list = [] #Placeholder for all deleted interfacetemplates of existing devicetype
        imported_interfacetemplate_list = [] #Placeholder for all imported interfacetemplates of existing devicetype and imported devicetype
        updated_consoleporttemplate_list = [] #Placeholder for all updated consoleporttemplates of existing devicetype
        deleted_consoleporttemplate_list = [] #Placeholder for all deleted consoleporttemplates of existing devicetype
        imported_consoleporttemplate_list = [] #Placeholder for all imported consoleporttemplates of existing devicetype and imported devicetype
        updated_powerporttemplate_list = [] #Placeholder for all updated powerporttemplates of existing devicetype
        deleted_powerporttemplate_list = [] #Placeholder for all deleted powerporttemplates of existing devicetype
        imported_powerporttemplate_list = [] #Placeholder for all imported powerporttemplates of existing devicetype and imported devicetype

        #Iterates, searches, validates and categorizes the yaml input data and store them in a different list objects if found or not found
        for vendor in input_data:
            if vendor:
                for part_number in vendor['part_numbers']:
                    if part_number:
                        device_type_url = f"https://raw.githubusercontent.com/netbox-community/devicetype-library/master/device-types/{vendor['vendor']}/{part_number}"
                        try:
                            get_yml_url = requests.get(f"{device_type_url}.yml")
                            get_yaml_url = requests.get(f"{device_type_url}.yaml")
                        except requests.exceptions.ConnectionError as error:
                            self.log_failure(error)
                            return
                        get_url_data = None
                        for get_data in [get_yml_url, get_yaml_url]:
                            #Checks if user provided partnumber is found in devicetype-library git repo
                            if get_data.ok:
                                get_url_data = get_data
                        #Store the URL data as DeviceTypeHandler class object in the list object
                        if get_url_data:
                            device_type = DeviceTypeHandler(
                                manufacturer = vendor['vendor'],
                                part_number = part_number,
                                yaml_template = get_url_data.text,
                                update_existing_record = data['update_existing_record'],
                            )
                            in_library_list.append(device_type)
                        else:
                            device_type = DeviceTypeHandler(
                                manufacturer = vendor['vendor'],
                                part_number = part_number,
                            )
                            not_in_library_list.append(device_type)
                    else:
                        self.log_failure(
                            f"No part_number found for vendor {vendor['vendor']} in the yaml file."
                        )
                        return
            else:
                self.log_failure(
                    f"No vendor name found in one of the vendor list in the yaml file."
                )
                return

        #Iterates the list of DeviceTypeHandler objects in found partnumber list
        for item in in_library_list:
            #Import or update the DeviceTypeHandler object
            item.import_record()

            updated_interfacetemplate_list += item.updated_interfacetemplates
            deleted_interfacetemplate_list += item.deleted_interfacetemplates
            imported_interfacetemplate_list += item.imported_interfacetemplates
            updated_consoleporttemplate_list += item.updated_consoleporttemplates
            deleted_consoleporttemplate_list += item.deleted_consoleporttemplates
            imported_consoleporttemplate_list += item.imported_consoleporttemplates
            updated_powerporttemplate_list += item.updated_powerporttemplates
            deleted_powerporttemplate_list += item.deleted_powerporttemplates
            imported_powerporttemplate_list += item.imported_powerporttemplates

            operations = [
                item.updated_interfacetemplates,
                item.deleted_interfacetemplates,
                item.imported_interfacetemplates,
                item.updated_consoleporttemplates,
                item.deleted_consoleporttemplates,
                item.imported_consoleporttemplates,
                item.updated_powerporttemplates,
                item.deleted_powerporttemplates,
                item.imported_powerporttemplates,
            ]

            #Store the DeviceTypeHandler object in a list object depending on the operation mode - import, update or none   
            if item.operation_mode:
                imported_devicetype_list.append(item)
            else:
                counter = 0
                for i in operations:
                        if len(i) != 0:
                            counter += 1
                if counter != 0:
                    updated_devicetype_list.append(item)
                else:
                    up_to_date_devicetype_list.append(item)

        #Generates the output report summary
        file_loader = FileSystemLoader('/opt/netbox/netbox/scripts/netbox_script/templates')
        env = Environment(loader=file_loader)
        template = env.get_template('devicetype_import_report.j2')
        context = {
            'in_library_list': in_library_list,
            'not_in_library_list': not_in_library_list,
            'imported_devicetype_list': imported_devicetype_list,
            'updated_devicetype_list': updated_devicetype_list,
            'up_to_date_devicetype_list': up_to_date_devicetype_list,
            'updated_interfacetemplate_list': updated_interfacetemplate_list,
            'deleted_interfacetemplate_list': deleted_interfacetemplate_list,
            'imported_interfacetemplate_list': imported_interfacetemplate_list,
            'updated_consoleporttemplate_list': updated_consoleporttemplate_list,
            'deleted_consoleporttemplate_list': deleted_consoleporttemplate_list,
            'imported_consoleporttemplate_list': imported_consoleporttemplate_list,
            'updated_powerporttemplate_list': updated_powerporttemplate_list,
            'deleted_powerporttemplate_list': deleted_powerporttemplate_list,
            'imported_powerporttemplate_list': imported_powerporttemplate_list,
        }
        output = template.render(context)
        return output