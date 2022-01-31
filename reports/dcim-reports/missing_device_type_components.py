# Identify devices which are missing components from the device type definition
from dcim.models import Device
from extras.reports import Report


class MissingDeviceTypeComponents(Report):
    name = "Missing Device Type Components"
    description = (
        "Find devices which are missing components that are in the device type template"
    )

    def test_add_ports(self):
        for device in Device.objects.all():
            dt = device.device_type

            for item, templateitem in [
                ("consoleports", "consoleporttemplates"),
                ("consoleserverports", "consoleserverporttemplates"),
                ("powerports", "powerporttemplates"),
                ("poweroutlets", "poweroutlettemplates"),
                ("interfaces", "interfacetemplates"),
                ("rearports", "rearporttemplates"),
                ("frontports", "frontporttemplates"),
                ("devicebays", "devicebaytemplates"),
            ]:
                names = {i.name for i in getattr(device, item).all()}
                templatenames = {i.name for i in getattr(dt, templateitem).all()}
                missing = templatenames - names
                if missing:
                    self.log_warning(device, "Missing %s %r" % (item, sorted(missing)))
