from dcim.constants import DEVICE_STATUS_ACTIVE
from dcim.models import Device
from virtualization.models import VirtualMachine
from virtualization.constants import *
from ipam.constants import *
from ipam.models import IPAddress, Prefix, VRF, VLAN
from extras.reports import Report
from collections import defaultdict

LOOPBACK_ROLES = [
    IPADDRESS_ROLE_LOOPBACK,
    IPADDRESS_ROLE_ANYCAST,
    IPADDRESS_ROLE_VIP,
    IPADDRESS_ROLE_VRRP,
]

# CheckPrimaryAddress reports forked from https://gist.github.com/candlerb/5380a7cdd03b60fbd02a664feb266d44
class CheckPrimaryAddressDevice(Report):
    description = "Check that every device with an assigned IP has a primary IP address assigned"

    def test_device_primary_ips(self):
        for device in Device.objects.filter(status=DEVICE_STATUS_ACTIVE).prefetch_related('interfaces__ip_addresses').all():
            fail = False
            intcount = 0
            all_addrs = {4: [], 6: []}
            for interface in device.interfaces.all():
                if not interface.mgmt_only:
                    intcount += 1
                    for addr in interface.ip_addresses.exclude(status=IPADDRESS_STATUS_DEPRECATED).all():
                        all_addrs[addr.family].append(addr)
            # There may be dumb devices with no interfaces / IP addresses, that's OK
            if not device.primary_ip4 and all_addrs[4]:
                self.log_failure(device, "Device has no primary IPv4 address (could be %s)" %
                              " ".join([str(a) for a in all_addrs[4]]))
                fail = True
            if not device.primary_ip6 and all_addrs[6]:
                self.log_failure(device, "Device has no primary IPv6 address (could be %s)" %
                              " ".join([str(a) for a in all_addrs[6]]))
                fail = True
            if not fail:
                # There may be dumb devices that are used as patch panels. Check for front/back ports
                if device.frontports.count() > 0 and device.rearports.count() > 0:
                    self.log_success(device)
                elif intcount == 0:
                    self.log_warning(device, "No interfaces assigned to device")
                else:
                    if len(all_addrs[4]) + len(all_addrs[6]) == 0:
                        self.log_warning(device, "No IP assigned to device")
                    else:
                        self.log_success(device)

class CheckPrimaryAddressVM(Report):
    description = "Check that every vm with an assigned IP has a primary IP address assigned"

    def test_vm_primary_ips(self):
        for vm in VirtualMachine.objects.filter(status=DEVICE_STATUS_ACTIVE).prefetch_related('interfaces__ip_addresses').all():
            fail = False
            intcount = 0
            all_addrs = {4: [], 6: []}
            for interface in vm.interfaces.all():
                if not interface.mgmt_only:
                    intcount += 1
                    for addr in interface.ip_addresses.exclude(status=IPADDRESS_STATUS_DEPRECATED).all():
                        all_addrs[addr.family].append(addr)
            # A VM is useless without an IP address
            if not all_addrs[4] and not all_addrs[6]:
                self.log_failure(vm, "Virtual machine has no IP addresses")
                continue
            if not vm.primary_ip4 and all_addrs[4]:
                self.log_failure(vm, "Virtual machine has no primary IPv4 address (could be %s)" %
                              " ".join([str(a) for a in all_addrs[4]]))
                fail = True
            if not vm.primary_ip6 and all_addrs[6]:
                self.log_failure(vm, "Virtual machine has no primary IPv6 address (could be %s)" %
                              " ".join([str(a) for a in all_addrs[6]]))
                fail = True
            if not fail:
                if intcount == 0:
                    self.log_warning(vm, "No interfaces assigned to vm")
                else:
                    self.log_success(vm)
