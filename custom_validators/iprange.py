#
# This file includes two custom validators that check for overlaps
# between IP ranges and IP addresses:
# - CheckAddressNotInRange, which validates that an IP address is not in any
#   existing IP range,
# - CheckRangeDoesNotIncludeAddress, which validates than an IP Range
#   does not include any existing IP address.
#
# Usage:
#
# Create a "validators" directory in netbox and copy this file into it:
#
#    mkdir -p /opt/netbox/netbox/validators
#    cp iprange.py /opt/netbox/netbox/validators
#
# Activate the validators by adding the following lines to
# /opt/netbox/netbox/netbox/configuration.py:
#
#        from validators.iprange import CheckAddressNotInRange, CheckRangeDoesNotIncludeAddress
#        CUSTOM_VALIDATORS = {
#            "ipam.ipaddress": ( CheckAddressNotInRange(), ),
#            "ipam.iprange": ( CheckRangeDoesNotIncludeAddress(), ),
#        }
#
from extras.validators import CustomValidator
from django.db.models import Q
import netaddr


#
# Check if an IP address is included in an existing IP range
#
def address_in_range(ip):
    from ipam.models.ip import IPRange

    try:
        including_ranges = IPRange.objects.filter(vrf=ip.vrf).filter(
            Q(start_address__lte=ip.address) & Q(end_address__gte=ip.address)
        )
        if including_ranges.exists():
            return including_ranges.first()
    except:
        pass

    return None


#
# Check if a range includes an existing IP address
#
def range_includes_address(rg):
    from ipam.models.ip import IPAddress

    try:
        start = rg.start_address
        end = rg.end_address
        included_addresses = IPAddress.objects.filter(vrf=rg.vrf).filter(
            Q(address__gte=start) & Q(address__lte=end)
        )
        if included_addresses.exists():
            return list([str(ip) for ip in included_addresses])
    except:
        pass

    return None


class CheckAddressNotInRange(CustomValidator):
    """Make sure an IP address is not in any existing IP range. Usage:

    from validators.iprange import CheckAddressNotInRange
    CUSTOM_VALIDATORS = {
            "ipam.ipaddress": ( CheckAddressNotInRange(), ),
    }
    """

    def validate(self, ip, instance):
        if (rg := address_in_range(ip)) is not None:
            self.fail(f"IP address '{ip}' used in range '{rg}'", field="address")


class CheckRangeDoesNotIncludeAddress(CustomValidator):
    """Make sure an IP Range does not include any existing IP address. Usage:

    from validators.iprange import CheckRangeDoesNotIncludeAddress
    CUSTOM_VALIDATORS = {
        "ipam.iprange": ( CheckRangeDoesNotIncludeAddress(), ),
    }
    """

    def validate(self, iprange, instance):
        if (addresses := range_includes_address(iprange)) is not None:
            msg = f"Range '{iprange}' includes existing addresses: {addresses}"
            self.fail(msg, field="start_address")
