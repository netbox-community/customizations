"""
This script adds missing components from the device type to selected device(s)
"""

from dcim.models import (Device, ConsolePort, ConsoleServerPort, PowerPort,
                         PowerOutlet, Interface, RearPort, FrontPort,
                         DeviceBay, ModuleBay)
from extras.scripts import Script, MultiObjectVar


class AddDeviceTypeComponents(Script):
    class Meta:
        name = "Add Device Type Components"
        description = "Add missing components to selected devices"

    devices = MultiObjectVar(
        model=Device,
    )

    def run(self, data, commit):
        for device in data["devices"]:
            dt = device.device_type

            # Based on Device.save():
            # "If this is a new Device, instantiate all of the related
            # components per the DeviceType definition"
            # Note that ordering is important: e.g. PowerPort before
            # PowerOutlet, RearPort before FrontPort
            for klass, item, templateitem in [
                (ConsolePort, 'consoleports', 'consoleporttemplates'),
                (ConsoleServerPort, 'consoleserverports',
                 'consoleserverporttemplates'),
                (PowerPort, 'powerports', 'powerporttemplates'),
                (PowerOutlet, 'poweroutlets', 'poweroutlettemplates'),
                (Interface, 'interfaces', 'interfacetemplates'),
                (RearPort, 'rearports', 'rearporttemplates'),
                (FrontPort, 'frontports', 'frontporttemplates'),
                (DeviceBay, 'devicebays', 'devicebaytemplates'),
                (ModuleBay, 'modulebays', 'modulebaytemplates'),
            ]:
                names = {i.name for i in getattr(device, item).all()}
                templates = getattr(dt, templateitem).all()
                items = [
                    x.instantiate(device=device)
                    for x in templates
                    if x.name not in names
                ]
                if items:
                    for i in items:
                        i.full_clean()
                    klass.objects.bulk_create(items)
                    self.log_success("%s (%d): created %d %s" % (device.name,
                                                                 device.id,
                                                                 len(items),
                                                                 item))
