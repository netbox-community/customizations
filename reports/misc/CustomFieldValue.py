from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from extras.reports import Report

# This sample looks for a custom field named "Monitor" and then acts from there

class Check_IfMonitored(Report):
    description = "Check if device is flagged to be monitored"

    def test_monitoring_enabled(self):
        for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
            monitor = device.cf.get("Monitor")
            if monitor is True:
                self.log_success(device)
            elif monitor is False:
                self.log_info(device, "Device set to not monitor")
            else:
                self.log_warning(device, "Device has null monitoring field")
