from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from extras.reports import Report
from extras.models import CustomFieldValue, CustomField

# This sample looks for a custom field named "Monitor" and then acts from there

class Check_IfMonitored(Report):
    description = "Check if device is flagged to be monitored"

    def test_monitoring_enabled(self):
        for mf in CustomField.objects.filter(name='Monitor'):
            MONITOR_FIELD = mf.id
        for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
            for monitor in CustomFieldValue.objects.filter(obj_id=device.id).filter(field_id=MONITOR_FIELD):
                if monitor.value is True:
                    self.log_success(device)
                elif monitor.value is False:
                    self.log_info(device, "Device set to not monitor")
                else:
                    self.log_warning(device, "Device has null monitoring field")
