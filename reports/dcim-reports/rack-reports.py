from dcim.constants import *
from dcim.models import Device, Rack, RackGroup
from extras.reports import Report
from ipam.constants import *

class DeviceRackingReport(Report):
    description = "Verify each device is assigned to a Rack"
    def test_device_racking(self):
        for device in Device.objects.filter(status=DEVICE_STATUS_ACTIVE):
            if device.rack_id is not None:
                if device.position is not None:
                    self.log_success(device)

                elif device.device_type.is_child_device:
                    self.log_info(device, "Device is child device and therefore not racked itself")
                else:
                    self.log_warning(device, "Device is racked, but not assigned a position")
            else:
                self.log_failure(device, "Device is not racked")

class RackGroupAssignmentReport(Report):
    description = "Verify each rack is assigned to a Rack Group"
    def test_rack_group_assignment(self):
        for rack in Rack.objects.all():
            if rack.group_id is not None:
                self.log_success(rack.name)
            else:
                self.log_failure(rack.name, "No Rack Group assigned")
