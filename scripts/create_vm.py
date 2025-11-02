"""
This script allows you to create a VM, an interface and primary IP address
all in one screen.

Workaround for issues:
https://github.com/netbox-community/netbox/issues/1492
https://github.com/netbox-community/netbox/issues/648
"""

from dcim.models import DeviceRole, Platform, MACAddress
from django.core.exceptions import ObjectDoesNotExist
from extras.models import Tag
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress, VRF
from tenancy.models import Tenant
from virtualization.choices import VirtualMachineStatusChoices
from virtualization.models import Cluster, VirtualMachine, VMInterface, VirtualDisk
from extras.scripts import Script, StringVar, IPAddressWithMaskVar, ObjectVar, MultiObjectVar, ChoiceVar, IntegerVar, TextVar

class NewVM(Script):
    class Meta:
        name = "New VM"
        description = "Create a new VM"

    vm_name = StringVar(label="VM name")
    dns_name = StringVar(label="DNS name", required=False)
    vm_tags = MultiObjectVar(model=Tag, label="VM tags", required=False)
    primary_ip4 = IPAddressWithMaskVar(label="IPv4 address")
    #primary_ip4_tags = MultiObjectVar(model=Tag, label="IPv4 tags", required=False)
    primary_ip6 = IPAddressWithMaskVar(label="IPv6 address", required=False)
    #primary_ip6_tags = MultiObjectVar(model=Tag, label="IPv6 tags", required=False)
    #vrf = ObjectVar(model=VRF, required=False)
    role = ObjectVar(model=DeviceRole, query_params=dict(vm_role=True), required=False)
    status = ChoiceVar(VirtualMachineStatusChoices, default=VirtualMachineStatusChoices.STATUS_ACTIVE)
    cluster = ObjectVar(model=Cluster)
    tenant = ObjectVar(model=Tenant, required=False)
    platform = ObjectVar(model=Platform, required=False)
    interface_name = StringVar(default="eth0")
    mac_address = StringVar(label="MAC address", required=False)
    vcpus = IntegerVar(label="VCPUs", required=False)
    memory = IntegerVar(label="Memory (MB)", required=False)
    disk_name = StringVar(label="Disk Name", required=False)
    disk_size = IntegerVar(label="Disk (MB)", required=False)
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
            comments=data["comments"],
            tenant=data.get("tenant"),
        )
        vm.full_clean()
        vm.save()
        vm.tags.set(data["vm_tags"])

        vminterface = VMInterface(
            name=data["interface_name"],
            virtual_machine=vm
        )
        vminterface.full_clean()
        vminterface.save()

        if data["mac_address"]:
            vmmacaddr = MACAddress(
                mac_address = data["mac_address"],
                assigned_object = vminterface
            )
            vmmacaddr.full_clean()
            vmmacaddr.save()
            setattr(vminterface, "primary_mac_address", vmmacaddr)
            vminterface.full_clean()
            vminterface.save()

        if data["disk_name"]:
            vmdisk = VirtualDisk(
                name=data["disk_name"],
                virtual_machine=vm,
                size=data["disk_size"]
            )
            vmdisk.full_clean()
            vmdisk.save()

        def add_addr(addr, family):
            if not addr:
                return
            if addr.version != family:
                raise RuntimeError(f"Wrong family for {a}")
            try:
                a = IPAddress.objects.get(
                    address=addr,
                    vrf=data.get("vrf"),
                )
                a.snapshot()
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
                raise RuntimeError(f"Address {addr} is already assigned")
            a.assigned_object = vminterface
            a.tenant = data.get("tenant")
            a.full_clean()
            a.save()
            #a.tags.set(data[f"primary_ip{family}_tags"])
            self.log_info(f"{result} IP address {a.address} {a.vrf or ''}")
            setattr(vm, f"primary_ip{family}", a)

        vm.snapshot()
        add_addr(data["primary_ip4"], 4)
        add_addr(data["primary_ip6"], 6)
        vm.full_clean()
        vm.save()
        self.log_success(f"Created VM [{vm.name}](/virtualization/virtual-machines/{vm.id}/)")
