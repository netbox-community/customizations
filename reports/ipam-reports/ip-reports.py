from dcim.constants import DEVICE_STATUS_ACTIVE
from dcim.models import Device
from virtualization.models import VirtualMachine
from virtualization.constants import *
from ipam.constants import *
from ipam.models import IPAddress, Prefix, VRF, VLAN
from extras.reports import Report
from collections import defaultdict
from django.db.models import Q

LOOPBACK_ROLES = [
    IPADDRESS_ROLE_LOOPBACK,
    IPADDRESS_ROLE_ANYCAST,
    IPADDRESS_ROLE_VIP,
    IPADDRESS_ROLE_VRRP,
]

class DeviceIPReport(Report):
    description = "Check that every device has either an IPv4 or IPv6 primary address assigned"

    def test_primary_ip4(self):
        for device in Device.objects.filter(status=DEVICE_STATUS_ACTIVE):
            intcount = 0
            for interface in device.interfaces.all():
                if not interface.mgmt_only:
                    intcount += 1
            # There may be dumb devices with no interfaces so no IP addresses, that's OK
            if intcount == 0:
                if device.primary_ip4_id is not None:
                    if device.primary_ip6_id is not None:
                        self.log_failure(device, "Device has primary IPv4 and IPv6 address but no interfaces")
                    else:
                        self.log_warning(device, "Device has missing primary IPv4 addresses but no interfaces")
                else:
                    self.log_success(device)
            elif device.primary_ip4_id is None:
                if device.device_type.is_child_device is True:
                    self.log_success(device)
                else:
                    if device.primary_ip6_id is None:
                        self.log_failure(device, "Device is missing primary IPv4 and IPv6 address")
                    else:
                        self.log_warning(device, "Device is missing primary IPv4 addresses")
            else:
                if device.device_type.is_child_device is True:
                    self.log_success(device)
                else:
                    if device.primary_ip6_id is None:
                        self.log_info(device, "Device is missing primary IPv6 address")
                    else:
                        self.log_success(device)

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

# CheckPrefixLength forked from https://gist.github.com/candlerb/5380a7cdd03b60fbd02a664feb266d44
class CheckPrefixLength(Report):
    description = "Check each IP address has the prefix length of the enclosing subnet"

    def test_prefix_lengths(self):
        prefixes = list(Prefix.objects.all())
        prefixes.sort(key=lambda k: k.prefix)   # overlapping subnets sort in order from largest to smallest
        for ipaddr in IPAddress.objects.all():
            a = ipaddr.address
            if str(a).startswith("fe80"):
                self.log_success(ipaddr)
                continue
            if ipaddr.family != a.version:
                self.log_failure(ipaddr, "family (%d) inconsistent with address.version (%d)" %
                                 (ipaddr.family, a.version))
                continue
            # We allow loopback-like things to be single address *or* have the parent prefix length
            if ipaddr.role in LOOPBACK_ROLES and (
                     (a.version == 4 and a.prefixlen == 32) or
                     (a.version == 6 and a.prefixlen == 128)):
                self.log_success(ipaddr)
                continue
            parents = [p for p in prefixes if
                              (p.vrf and p.vrf.id) == (ipaddr.vrf and ipaddr.vrf.id) and
                               p.prefix.version == a.version and a.ip in p.prefix]
            if not parents:
                self.log_info(ipaddr, "No parent prefix")
                continue
            parent = parents[-1]
            if a.prefixlen != parent.prefix.prefixlen:
                self.log_failure(ipaddr, "prefixlen (%d) inconsistent with parent prefix (%s)" %
                                 (a.prefixlen, str(parent.prefix)))
                continue
            # if the parent prefix also contains child prefixes, that probably means that
            # an intermediate parent prefix is missing
            pchildren = [p for p in prefixes if
                                (p.vrf and p.vrf.id) == (parent.vrf and parent.vrf.id) and
                                 p.prefix.version == parent.prefix.version and
                                 p.prefix != parent.prefix and
                                 p.prefix in parent.prefix]
            if pchildren:
                self.log_warning(ipaddr, "parent prefix (%s) contains %d other child prefix(es)" %
                                 (str(parent.prefix), len(pchildren)))
                continue
            self.log_success(ipaddr)


# UniqueIPReport was forked from https://gist.github.com/dgarros/acc23b4fd8d42844b8a41f695e6cb769
class UniqueIPReport(Report):
    description = "Validate that we don't have an IP address allocated twice in the network"

    def test_unique_ip(self):
        already_found = []
        for ip in IPAddress.objects.exclude(Q(role=IPADDRESS_ROLE_ANYCAST) | Q(role=IPADDRESS_ROLE_VIP) | Q(role=IPADDRESS_ROLE_VRRP)):
            if ip.address in already_found:
               continue
            elif not ip.interface:
                continue
            duplicates = ip.get_duplicates()
            real_dup = 0
            for duplicate in duplicates:
                if duplicate.interface:
                    real_dup +=1
            if real_dup != 0:
                already_found.append(ip.address)
                msg = "has %s duplicate ips" % real_dup
                self.log_failure( ip, msg )
