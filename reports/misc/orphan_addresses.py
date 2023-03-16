# Useful to find Devices or VirtualMachines with primary ip addresses that are not assigned to any interface.

from virtualization.models import VirtualMachine
from dcim.models import Device
from extras.reports import Report

class OrphanIPAddress(Report):

    description = "Find Models with orphan IP addresses"

    def test_vm_orphan_ip(self):
        for vm in VirtualMachine.objects.filter(primary_ip4__isnull=False):
            if vm.interfaces.filter(id=vm.primary_ip4.assigned_object_id).count() == 0:
                self.log_failure(vm, f"VM has orphan IP address {vm.primary_ip4}")

    def test_device_orphan_ip(self):
        for device in Device.objects.filter(primary_ip4__isnull=False):
            if device.interfaces.filter(id=device.primary_ip4.assigned_object_id).count() == 0:
                self.log_failure(device, f"Device has orphan IP address {device.primary_ip4}")
