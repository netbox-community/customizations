import re

from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from extras.reports import Report

# A modified John Anderson's NetBox Day 2020 Presentation by adding a check for all sites, not just LAX
# All credit goes to @lampwins

class DeviceHostnameReport(Report):
   description = "Verify each device conforms to naming convention Example: spin-(site_name)-0001 or leaf-(site_name)-0001-a"

   def test_devices_naming(self):
       for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
           # Change the naming standard based on the re.match
           if re.match("[a-z]{4}-" + str(device.site.name) + "-[0-9]{4}(-[a-b])?", str(device.name) , re.IGNORECASE):
               self.log_success(device)
           else:
               self.log_failure(device, "Hostname does not conform to standard!")
