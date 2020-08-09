"""
This script allows you to used in conjunction with the project
netbox-community/devicetype-library to automatically create all
content related to devicetype defined therein..

Workaround for issues:
https://github.com/netbox-community/reports/issues/35
"""

import os
import yaml

from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import (DeviceType, Manufacturer, ConsolePortTemplate,
                         PowerPortTemplate, PowerOutletTemplate,
                         InterfaceTemplate)
from extras.scripts import *


class DeviceTypeInit(Script):

    class Meta:
        name = 'Device Type Init'
        description = 'Initialize device type from yaml file'
        field_order = ['ManufacturersSelection']

    device_type_choices = (('ALL', 'ALL'),)
    device_type_path = '/'.join((os.getcwd(),
                                 'scripts',
                                 'device-types'))
    for _, dir_list, _ in os.walk(device_type_path):
        if dir_list != []:
            for dir_name in dir_list:
                device_type_choices += ((dir_name, dir_name),)

    ManufacturersSelection = ChoiceVar(choices = device_type_choices)

    def run(self, data, commit):
        if data['ManufacturersSelection'] == 'ALL':
            device_type_path = '/'.join((os.getcwd(),
                                         'scripts',
                                         'device-types'))
            for root_path, dir_list, file_list in os.walk(device_type_path):
                if dir_list is not None:
                    for dir_name in dir_list:
                        manufacturer = Manufacturer(
                            name = dir_name,
                            slug = slugify(dir_name)
                        )
                        try:
                            with transaction.atomic():
                                manufacturer.save()
                        except IntegrityError:
                            self.log_info('Existing manufacturer: {}'.\
                                format(manufacturer))
                        else:
                            self.log_success('Created new manufacturer: {}'.\
                                format(manufacturer))
                for file in file_list:
                    path = os.path.join(root_path, file)
                    with open(path, 'r') as f:
                        data = yaml.load(f)
                        self.create_dev_type_and_add_temp(data)
        else:
            manufacturer = data['ManufacturersSelection']
            device_type_file_path = '/'.join((os.getcwd(),
                                              'scripts',
                                              'device-types',
                                              manufacturer))
            manufacturer = Manufacturer(
                name = manufacturer,
                slug = slugify(manufacturer)
            )
            try:
                with transaction.atomic():
                    manufacturer.save()
            except IntegrityError:
                self.log_info('Existing manufacturer: {}'.\
                    format(manufacturer))
            else:
                self.log_success('Created new manufacturer: {}'.\
                    format(manufacturer))
            for root_path, dir_list, file_list in os.walk(device_type_file_path):
                for file in file_list:
                    path = os.path.join(root_path, file)
                    with open(path, 'r') as f:
                        data = yaml.load(f)
                        self.create_dev_type_and_add_temp(data)
    
    def create_dev_type_and_add_temp(self, data):
        device_type = DeviceType(
            manufacturer = Manufacturer.objects.get(
                name = data.get('manufacturer')),
            model = data.get('model'),
            slug = data.get('slug'),
            part_number = data.get('part_number', ''),
            u_height = data.get('u_height', 1),
            is_full_depth = data.get('is_full_depth', True),
            comments = data.get('comments', '')
        )
        try:
            with transaction.atomic():
                device_type.save()
        except IntegrityError:
            self.log_info('Existing device type: {}'.\
                format(device_type))
        else:
            self.log_success('Created new device type: {}'.\
                format(device_type))

        # Reacquire device type to get device_type_id
        device_type = DeviceType.objects.get(model=data['model'])

        if 'console-ports' in data:
            console_port_temp_list = []
            for console_port in data['console-ports']:
                console_port_temp = ConsolePortTemplate(
                    name = console_port['name'],
                    type = console_port['type'],
                    device_type = device_type
                )
                console_port_temp_list.append(
                    console_port_temp)
            try:
                with transaction.atomic():
                    ConsolePortTemplate.objects.bulk_create(
                        tuple(console_port_temp_list))
            except IntegrityError:
                self.log_info('Console ports already '
                              'exists, Please check '
                              'manually.')
        
        if 'power-ports' in data:
            power_port_temp_list = []
            for power_port in data['power-ports']:
                power_port_temp = PowerPortTemplate(
                    name = power_port['name'],
                    type = power_port['type'],
                    device_type = device_type
                )
                power_port_temp_list.append(
                    power_port_temp)
            try:
                with transaction.atomic():
                    PowerPortTemplate.objects.bulk_create(
                        tuple(power_port_temp_list))
            except IntegrityError:
                self.log_info('Power ports already '
                              'exists, Please check '
                              'manually.')
        
        if 'power-outlets' in data:
            power_outlet_temp_list = []
            for power_outlet in data['power-outlets']:
                power_outlet_temp = PowerOutletTemplate(
                    name = power_outlet['name'],
                    type = power_outlet['type'],
                    device_type = device_type
                )
                power_outlet_temp_list.append(
                    power_outlet_temp)
            try:
                with transaction.atomic():
                    PowerOutletTemplate.objects.bulk_create(
                        tuple(power_outlet_temp_list))
            except IntegrityError:
                self.log_info('Power outlets already '
                              'exists, Please check '
                              'manually.')
        
        if 'interfaces' in data:
            interface_temp_list = []
            for interface in data['interfaces']:
                interface_temp = InterfaceTemplate(
                    name = interface['name'],
                    type = interface['type'],
                    device_type = device_type,
                    mgmt_only = interface.get(
                        'mgmt_only', False)
                )
                interface_temp_list.append(interface_temp)
            try:
                with transaction.atomic():
                    InterfaceTemplate.objects.bulk_create(
                        tuple(interface_temp_list))
            except IntegrityError:
                self.log_info('Power outlets already '
                              'exists, Please check '
                              'manually.')
