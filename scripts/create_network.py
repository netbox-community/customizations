# SPDX-FileCopyrightText: 2021 Robin Schneider <ypid@riseup.net>
#
# SPDX-License-Identifier: MIT

"""
NetBox 2.11 custom script to create a network segment on a Firewall.

The script assumes the following exists:

* Site
* Device Role "Firewall" exists.
* Firewall device with physical Interface.
* VLAN Group per Site
* VLAN/Prefix Role per Site
* Prefix container per Site

The script does the following:

* Reuse or create a VLAN. The VID is derived from the prefix IP Address if a
  new VLAN is created.
* Reuse or create a Prefix. If no Prefix is assigned to the VLAN already the
  next available network block from the Prefix container is created.
* Reuse or create a IP Address for the Firewall Interface.
  If not existing, the first usable IP of the Prefix is used.
* Reuse Interface on the Firewall. Create it only if sub interface for tagged mode.
  Assign the VLAN and IP Address to the Interface.

Bugs:

* IPv6 is not yet supported. But it is simple to implement.
  Just let NetBox pick the next free VLAN and Prefix and drop the need for them
  to have the same numbers. That is just my legacy.
"""

from django.db.utils import IntegrityError
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from dcim.models import Site, Device, Interface
from dcim.choices import InterfaceTypeChoices, InterfaceModeChoices
from ipam.models import Role, VLANGroup, VLAN, Prefix, IPAddress
from ipam.choices import PrefixStatusChoices
from virtualization.models import VirtualMachine, VMInterface
from extras.scripts import Script, ObjectVar, StringVar, IntegerVar, ChoiceVar


class NewNetworkSegment(Script):
    class Meta:
        name = "New segment"
        description = "Create a new network segment."
        commit_default = False

    site = ObjectVar(
        model=Site,
    )
    # Derived from other user input in _get_site_prefix_container().
    #  prefix_container = ObjectVar(
    #      model=Prefix,
    #      query_params={
    #          'status': 'container',
    #          'site_id': '$site',
    #      },
    #      required=False,
    #  )
    firewall = ObjectVar(
        model=Device,
        query_params={
            'status': 'active',
            'role': 'firewall',
            'site_id': '$site',
        },
        required=False,
    )
    firewall2 = ObjectVar(
        model=VirtualMachine,
        query_params={
            'status': 'active',
            'role': 'firewall',
            'site_id': '$site',
        },
        required=False,
    )
    interface = ObjectVar(
        model=Interface,
        query_params={
            'type__n': 'virtual',
            'device_id': '$firewall',
        },
        required=False,
    )
    interface2 = ObjectVar(
        model=VMInterface,
        query_params={
            'virtual_machine_id': '$firewall2',
        },
        required=False,
    )
    vlan_name = StringVar(
        label="VLAN Name",
        max_length=64,
    )
    prefix_vlan_role = ObjectVar(
        model=Role,
        label="Prefix/VLAN Role",
        required=False,
    )
    ip_mask = IntegerVar(
        label="IP Address Mask Length",
        min_value=8,
        max_value=24,
        default=24,
    )
    interface_mode = ChoiceVar(
        label="Interface 802.1Q Mode",
        choices=(
            ('tagged', "Tagged"),
            ('access', "Access"),
        ),
    )

    def run(self, data, commit):
        site_vlan_group = self._get_vlan_group(data)
        new_vlan = self._ensure_vlan_exists_and_return(
            data,
            site_vlan_group,
        )
        new_prefix = self._ensure_prefix_exists_and_return(
            data,
            site_vlan_group,
            new_vlan,
        )
        new_ip_address = self._ensure_ip_address_exists_and_return(
            data,
            new_prefix,
        )

        if data['firewall'] is not None:
            firewall = data['firewall']
        elif data['firewall2'] is not None:
            firewall = data['firewall2']
        else:
            return

        if data['interface'] is not None:
            interface = data['interface']
        elif data['interface2'] is not None:
            interface = data['interface2']
        else:
            return

        if data['interface_mode'] == 'tagged':
            #  self.log_info(firewall)
            if firewall.platform.slug in ['opnsense', 'pfsense']:
                new_interface_name = f"{interface.name}_vlan{new_vlan.vid}"
            else:
                new_interface_name = f"{interface.name}.{new_vlan.vid}"
            new_interface = Interface(
                name=new_interface_name,
                parent=interface,
                device=firewall,
                type=InterfaceTypeChoices.TYPE_VIRTUAL,
                mode=InterfaceModeChoices.MODE_TAGGED,
            )
            try:
                with transaction.atomic():
                    new_interface.save()
            except IntegrityError:
                self.log_info(f"Interface already exists: {new_interface}")
            else:
                self.log_success(f"Created Interface: {new_interface}")

            new_interface = Interface.objects.get(
                device=firewall,
                name=new_interface_name,
            )
        else:
            new_interface = interface

        if data['interface_mode'] == 'tagged':
            if new_interface.mode != InterfaceModeChoices.MODE_TAGGED:
                raise Exception(f"Interface {new_interface} is not mode tagged. Please change this manually.")
            new_interface.tagged_vlans.add(new_vlan)
        else:
            if new_interface.mode != InterfaceModeChoices.MODE_ACCESS:
                raise Exception(f"Interface {new_interface} is not mode access. Please change this manually.")
            new_interface.untagged_vlan = new_vlan

        new_interface.ip_addresses.clear()
        new_interface.ip_addresses.add(new_ip_address)
        new_interface.description = data['vlan_name']
        new_interface.save()
        self.log_success(f"Updated Interface: {new_interface}")

    def _ensure_vlan_exists_and_return(self, data, site_vlan_group):
        new_prefix_str = None
        new_vlan = VLAN.objects.filter(
            name=data['vlan_name'],
            group=site_vlan_group,
        )
        if new_vlan.count() == 1:
            new_vlan = new_vlan[0]
            self.log_info(f"VLAN already exists: {new_vlan}")
        else:
            #  if data['vlan_id']:
            new_prefix_str = self._get_first_available_prefix_variable_mask_length(data)
            new_vlan_id = self._derive_vlan_id_from_prefix_address(new_prefix_str)

            new_vlan = VLAN.objects.filter(
                vid=new_vlan_id,
                group=site_vlan_group,
            )
            if new_vlan.count() == 1:
                new_vlan = new_vlan[0]
                self.log_info(f"VLAN already exists: {new_vlan}")

            else:
                new_vlan = VLAN(
                    vid=new_vlan_id,
                    name=data['vlan_name'],
                    group=site_vlan_group,
                )
                new_vlan.save()
                self.log_success(f"Created VLAN: {new_vlan}")

        new_vlan.role = data['prefix_vlan_role']
        new_vlan.save()

        return new_vlan

    def _ensure_prefix_exists_and_return(self, data, site_vlan_group, new_vlan):
        new_prefix = Prefix.objects.filter(
            vlan__vid=new_vlan.vid,
            vlan__group=site_vlan_group,
        )
        if new_prefix.count() != 0:
            new_prefix = new_prefix[0]
            self.log_info(f"Prefix already exists on VLAN: {new_prefix}")
        else:
            new_prefix_str = self._derive_prefix_address_from_vlan_id(data, new_vlan.vid)

            new_prefix = Prefix(
                prefix=new_prefix_str,
            )
            try:
                with transaction.atomic():
                    new_prefix.save()
            except IntegrityError:
                self.log_info(f"Prefix already exists: {new_prefix}")
                new_prefix = Prefix.objects.get(
                    prefix=new_prefix_str,
                    role=data['prefix_vlan_role'],
                )
            else:
                self.log_success(f"Created prefix: {new_prefix}")

        new_prefix.role = data['prefix_vlan_role']
        new_prefix.site = data['site']
        new_prefix.vlan = new_vlan
        new_prefix.save()

        # Workaround for new_prefix which is a str.
        new_prefix = Prefix.objects.get(pk=new_prefix.pk)

        return new_prefix

    def _ensure_ip_address_exists_and_return(self, data, new_prefix):
        prefix_ip_addresses = new_prefix.prefix.__iter__()

        if new_prefix.family == 4:
            # Skip network ID.
            next(prefix_ip_addresses)

        prefix_ip_address = next(prefix_ip_addresses)

        new_ip_address = IPAddress(
            address=f'{prefix_ip_address}/{new_prefix.prefix.prefixlen}',
        )
        try:
            with transaction.atomic():
                new_ip_address.save()
        except IntegrityError:
            self.log_info(f"IPAddress already exists: {new_ip_address}")
            new_ip_address = IPAddress.objects.get(
                address=prefix_ip_address,
            )
        else:
            self.log_success(f"Created IPAddress: {new_ip_address}")

        return new_ip_address

    def _get_site_prefix_container(self, data):
        site_prefix_container = Prefix.objects.filter(
            site=data['site'],
            status=PrefixStatusChoices.STATUS_CONTAINER,
        )
        if site_prefix_container.count() != 1:
            if data['prefix_vlan_role'] is not None:
                site_prefix_container = Prefix.objects.filter(
                    role__name=data['prefix_vlan_role'],
                    site=data['site'],
                    status=PrefixStatusChoices.STATUS_CONTAINER,
                )
            if site_prefix_container.count() != 1:
                raise Exception(f"{site_prefix_container.count()} prefix containers exist for this site. Expected 1.")
        return site_prefix_container[0]

    def _get_vlan_group(self, data):
        site_vlan_group = VLANGroup.objects.filter(
            scope_type=ContentType.objects.get_by_natural_key('dcim', 'site'),
            scope_id=data['site'].id,
        )
        if site_vlan_group.count() != 1:
            raise Exception(f"{site_vlan_group.count()} prefix containers exist for this site. Expected 1.")
        return site_vlan_group[0]

    def _get_first_available_prefix_variable_mask_length(self, data):
        site_prefix_container = self._get_site_prefix_container(data)
        available_prefixes = site_prefix_container.get_available_prefixes()
        for available_prefix in available_prefixes.iter_cidrs():
            if data['ip_mask'] >= available_prefix.prefixlen:
                return '{}/{}'.format(
                    available_prefix.network,
                    data['ip_mask'],
                )
                break

    def _derive_vlan_id_from_prefix_address(self, prefix_address):
        """172.23.42.0/24 -> VLAN ID: 2342"""

        new_vlan_id = 0
        for ip_octet in prefix_address.split('/')[0].split('.')[1:3]:
            new_vlan_id = 100 * new_vlan_id + int(ip_octet)
        self.log_info(f"Derived VLAN ID {new_vlan_id} from prefix {prefix_address}.")
        return new_vlan_id

    def _derive_prefix_address_from_vlan_id(self, data, vlan_id):
        """VLAN ID: 2342 -> 172.23.42.0/24 (depending on prefix container)"""

        site_prefix_container = self._get_site_prefix_container(data)

        ipv4_octets = (
            str(site_prefix_container.prefix).split('.')[0],
            str(int(vlan_id / 100)),
            str(vlan_id % 100),
            '0',
        )

        return '.'.join(ipv4_octets) + '/' + str(data['ip_mask'])
