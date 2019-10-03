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
