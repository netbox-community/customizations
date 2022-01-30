"""
This script allows you to create a VM, an interface and primary IP address
all in one screen.

Workaround for issues:
https://github.com/netbox-community/netbox/issues/1492
https://github.com/netbox-community/netbox/issues/648
"""
from dcim.models import DeviceRole
from dcim.models import Platform
from django.core.exceptions import ObjectDoesNotExist
from extras.scripts import ChoiceVar
from extras.scripts import IntegerVar
from extras.scripts import IPAddressWithMaskVar
from extras.scripts import ObjectVar
from extras.scripts import Script
from extras.scripts import StringVar
from extras.scripts import TextVar
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress
from ipam.models import VRF
from tenancy.models import Tenant
from virtualization.choices import VirtualMachineStatusChoices
from virtualization.models import Cluster
from virtualization.models import VirtualMachine
from virtualization.models import VMInterface


class NewVM(Script):
    class Meta:
        name = "New VM"
        description = "Create a new VM"
        field_order = [
            "vm_name",
            "dns_name",
            "primary_ip4",
            "primary_ip6",  #'vrf',
            "role",
            "status",
            "cluster",
            "tenant",
            "platform",
            "interface_name",
            "mac_address",
            "vcpus",
            "memory",
            "disk",
            "comments",
        ]

    vm_name = StringVar(label="VM name")
    dns_name = StringVar(label="DNS name", required=False)
    primary_ip4 = IPAddressWithMaskVar(label="IPv4 address")
    primary_ip6 = IPAddressWithMaskVar(label="IPv6 address", required=False)
    # vrf = ObjectVar(model=VRF, required=False)
    role = ObjectVar(model=DeviceRole, query_params=dict(vm_role=True), required=False)
    status = ChoiceVar(
        VirtualMachineStatusChoices, default=VirtualMachineStatusChoices.STATUS_ACTIVE
    )
    cluster = ObjectVar(model=Cluster)
    tenant = ObjectVar(model=Tenant, required=False)
    platform = ObjectVar(model=Platform, required=False)
    interface_name = StringVar(default="eth0")
    mac_address = StringVar(label="MAC address", required=False)
    vcpus = IntegerVar(label="VCPUs", required=False)
    memory = IntegerVar(label="Memory (MB)", required=False)
    disk = IntegerVar(label="Disk (GB)", required=False)
    comments = TextVar(label="Comments", required=False)

    def run(self, data, commit):
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
        vm.full_clean()
        vm.save()

        vminterface = VMInterface(
            name=data["interface_name"],
            mac_address=data["mac_address"],
            virtual_machine=vm,
        )
        vminterface.full_clean()
        vminterface.save()

        def add_addr(addr, expect_family):
            if not addr:
                return
            if addr.version != expect_family:
                raise RuntimeError("Wrong family for %r" % a)
            try:
                a = IPAddress.objects.get(
                    address=addr,
                    vrf=data.get("vrf"),
                )
                result = "Assigned"
            except ObjectDoesNotExist:
                a = IPAddress(
                    address=addr,
                    vrf=data.get("vrf"),
                )
                result = "Created"
            a.status = IPAddressStatusChoices.STATUS_ACTIVE
            a.dns_name = data["dns_name"]
            if a.assigned_object:
                raise RuntimeError("Address %s is already assigned" % addr)
            a.assigned_object = vminterface
            a.tenant = data.get("tenant")
            a.full_clean()
            a.save()
            self.log_info("%s IP address %s %s" % (result, a.address, a.vrf or ""))
            setattr(vm, "primary_ip%d" % a.family, a)

        add_addr(data["primary_ip4"], 4)
        add_addr(data["primary_ip6"], 6)
        vm.full_clean()
        vm.save()
        self.log_success("Created VM %s" % vm.name)
