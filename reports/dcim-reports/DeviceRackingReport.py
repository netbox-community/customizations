from dcim.choices import DeviceStatusChoices
from dcim.models import Device, Rack
from extras.reports import Report

class DeviceRackingReport(Report):
    description = "Verify each device is assigned to a Rack"
    def test_device_racking(self):
        for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
            if device.rack_id is not None:
                if device.position is not None:
                    self.log_success(device)

                elif device.device_type.is_child_device:
                    self.log_info(device, "Device is child device and therefore not racked itself")
                else:
                    self.log_warning(device, "Device is racked, but not assigned a position")
            else:
                self.log_failure(device, "Device is not racked")
