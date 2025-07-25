#!/usr/bin/python3

"""Validators library for NetBox scripts."""

from typing import Union

import netaddr
from dcim.models import Device, Interface
from scripts.common.errors import InvalidInput

################################################################################
#                        Validators for single values                          #
################################################################################


def validate_IP(field: str, ip: str) -> None:
    """Validate that the given ip is a valid IPv4 or IPv6 address.

    If it isn't raise an InvalidInput exception denoting the errornous value including the field name.
    """
    try:
        netaddr.IPAddress(ip)
    except Exception:
        raise InvalidInput(
            f'Given value "{ip}" for parameter "{field}" is not a valid IP address!'
        )


def validate_prefix(field: str, pfx: str) -> None:
    """Validate that the given pfx is a valid IPv4 or IPv6 address / prefix length.

    If it isn't raise an InvalidInput exception denoting the errornous value including the field name.
    """
    try:
        if "/" not in pfx:
            raise ValueError()
        netaddr.IPNetwork(pfx)
    except Exception:
        raise InvalidInput(
            f'Given value "{pfx}" for parameter "{field}" is not a valid IP prefix!'
        )


def validate_device_name(field: str, device_name: str) -> None:
    """Validate that the given device_name refers to an existing device in NetBox.

    If it isn't raise an InvalidInput exception denoting the errornous value including the field name.
    """
    try:
        Device.objects.get(name=device_name)
    except Device.DoesNotExist:
        raise InvalidInput(
            f'Given device name "{device_name}" (paramter "{field}") does not exist!'
        )


def validate_VLAN_ID(field: str, vid_str: str) -> None:
    """Validate that the given vid is a valid VLAN ID, meaning an integer value between 0 and 4096.

    If it isn't raise an InvalidInput exception denoting the errornous value including the field name.
    """
    try:
        vid = int(vid_str)
        if vid < 1 or vid > 4096:
            raise ValueError()
    except ValueError:
        raise InvalidInput(
            f'Given VLAN ID "{vid_str}" (parameter "{field}") is not a valid VLAN ID!'
        )


def validate_bool(field: str, boolean: any) -> None:
    """Validate that the given boolean is a valid boolean.

    If it isn't raise an InvalidInput exception denoting the errornous value including the field name.
    """
    if not isinstance(boolean, bool):
        raise InvalidInput(
            f'Given value "{boolean} (parameter "{field}") is not a valid boolean!'
        )


def validate_ASN(field: str, asn_str: str) -> None:
    """Validate that the given asn is a valid ASN, meaning an integer value between 1 and 2^32.

    If it isn't raise an InvalidInput Exception denoting the errornous value including the field name.
    """
    try:
        asn = int(asn_str)
        if asn < 1 or asn > 2**32:
            raise ValueError()
    except ValueError:
        raise InvalidInput(
            f'Given ASN "{asn_str}" (parameter "{field}") is not a valid ASN!'
        )


VALIDATOR_MAP = {
    "ip": validate_IP,
    "prefix": validate_prefix,
    "device_name": validate_device_name,
    "vlan_id": validate_VLAN_ID,
    "bool": validate_bool,
    "asn": validate_ASN,
}


################################################################################
#                      Validators to be applied manually                       #
################################################################################


def validate_IP_within_subnet(
    ip: Union[netaddr.ip.IPNetwork, str], pfx: Union[netaddr.ip.IPNetwork, str]
) -> None:
    """Validate that the given ip is a valid IPv4 or IPv6 address and lies within the given pfx.

    If ip or pfx aren't valid values or the ip doesn't lie within pfx, raise an InvalidInput exception.
    """
    if isinstance(pfx, str) and "/" not in pfx:
        raise InvalidInput(f"Invalid prefix {pfx}, no / present!")
    try:
        ip_obj = netaddr.IPAddress(ip)
        pfx_obj = netaddr.IPNetwork(pfx)
    except Exception:
        raise InvalidInput(
            f"Failed to parse IP {ip} or prefix {pfx}, while validating subnet alignment!"
        )

    if ip_obj not in pfx_obj:
        raise InvalidInput(f"IP address {ip} does not belong to subnet {pfx}")


def validate_prefixes_within_same_subnet(
    ip_a: Union[netaddr.ip.IPNetwork, str], ip_b: Union[netaddr.ip.IPNetwork, str]
) -> None:
    """Verify the two IPs are within the same IP subnet.

    If they are NOT within the same subnet or at least one of them fails to parse, raise an InvalidInput exception.
    """
    try:
        ip_a_obj = netaddr.IPNetwork(ip_a)
        ip_b_obj = netaddr.IPNetwork(ip_b)
    except Exception:
        raise InvalidInput(
            f"At least one of IPs/prefixes {ip_a} / {ip_b} is not a valid CIDR prefix!"
        )

    if ip_a_obj.network != ip_b_obj.network or ip_a_obj.prefixlen != ip_b_obj.prefixlen:
        raise InvalidInput(
            f"IPs/Prefixes {ip_a} and {ip_b} are not part of the same subnet!"
        )


def validate_device_interface(device: Device, iface: Interface) -> None:
    """Verify the given interface belongs to the given device.

    If not an InvalidInput exception is raised.
    """
    if iface.device != device:
        raise InvalidInput(
            f"Interface {iface.name} does not belong to device {device.name}!"
        )
