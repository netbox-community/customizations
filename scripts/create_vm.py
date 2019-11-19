"""
This script allows you to create a VM, an interface and primary IP address
all in one screen.

Workaround for issues:
https://github.com/netbox-community/netbox/issues/1492
https://github.com/netbox-community/netbox/issues/648
"""

from dcim.constants import DEVICE_STATUS_ACTIVE, IFACE_TYPE_VIRTUAL
from dcim.models import DeviceRole, Platform, Interface
from django.core.exceptions import ObjectDoesNotExist
from ipam.constants import IPADDRESS_STATUS_ACTIVE
from ipam.models import IPAddress, VRF
from tenancy.models import Tenant
from virtualization.constants import VM_STATUS_CHOICES
from virtualization.models import Cluster, VirtualMachine
from extras.scripts import Script, StringVar, IPNetworkVar, ObjectVar, ChoiceVar, IntegerVar, TextVar

class NewVM(Script):
    class Meta:
        name = "New VM"
        description = "Create a new VM"
        field_order = ['vm_name', 'dns_name', 'primary_ip4', 'primary_ip6', #'vrf',
                       'role', 'status', 'cluster', #'tenant',
                       'platform', 'interface_name', 'mac_address',
                       'vcpus', 'memory', 'disk', 'comments']

    vm_name = StringVar(label="VM name")
    dns_name = StringVar(label="DNS name", required=False)
    primary_ip4 = IPNetworkVar(label="IPv4 address")
    primary_ip6 = IPNetworkVar(label="IPv6 address", required=False)
    #vrf = ObjectVar(VRF.objects, required=False)
    role = ObjectVar(DeviceRole.objects.filter(vm_role=True))
    status = ChoiceVar(VM_STATUS_CHOICES, default=DEVICE_STATUS_ACTIVE)
    cluster = ObjectVar(Cluster.objects)
    #tenant = ObjectVar(Tenant.objects, required=False)
    platform = ObjectVar(Platform.objects, required=False)
    interface_name = StringVar(default="eth0")
    mac_address = StringVar(label="MAC address", required=False)
    vcpus = IntegerVar(label="VCPUs", required=False)
    memory = IntegerVar(label="Memory (MB)", required=False)
    disk = IntegerVar(label="Disk (GB)", required=False)
    comments = TextVar(label="Comments", required=False)

    def run(self, data):
        vm = VirtualMachine(
            name=data["vm_name"],
            role=data["role"],
            status=data["status"],
            cluster=data["cluster"],
            platform=data["platform"],
            vcpus=data["vcpus"],
            memory=data["memory"],
            disk=data["disk"],
            comments=data["comments"],
            tenant=data.get("tenant"),
        )
        vm.save()

        interface = Interface(
            name=data["interface_name"],
            type=IFACE_TYPE_VIRTUAL,
            mac_address=data["mac_address"],
            virtual_machine=vm,
        )
        interface.save()

        def add_addr(addr, expect_family):
            if not addr:
                return
            if addr.version != expect_family:
                raise RuntimeError("Wrong family for %r" % a)
            try:
                a = IPAddress.objects.get(
                    address=addr,
                    family=addr.version,
                    vrf=data.get("vrf"),
                )
                result = "Assigned"
            except ObjectDoesNotExist:
                a = IPAddress(
                   address=addr,
                   family=addr.version,
                   vrf=data.get("vrf"),
                )
                result = "Created"
            a.status = IPADDRESS_STATUS_ACTIVE
            a.dns_name = data["dns_name"]
            if a.interface:
                raise RuntimeError("Address %s is already assigned" % addr)
            a.interface = interface
            a.tenant = data.get("tenant")
            a.save()
            self.log_info("%s IP address %s %s" % (result, a.address, a.vrf or ""))
            setattr(vm, "primary_ip%d" % a.family, a)

        add_addr(data["primary_ip4"], 4)
        add_addr(data["primary_ip6"], 6)
        vm.save()
        self.log_success("Created VM %s" % vm.name)
