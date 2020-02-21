from ipam.choices import IPAddressRoleChoices
from ipam.models import IPAddress
from extras.reports import Report
from django.db.models import Q

# UniqueIPReport was forked from https://gist.github.com/dgarros/acc23b4fd8d42844b8a41f695e6cb769
class UniqueIPReport(Report):
    description = "Validate that we don't have an IP address allocated twice in the network"

    def test_unique_ip(self):
        already_found = []
        for ip in IPAddress.objects.exclude(Q(role=IPAddressRoleChoices.ROLE_ANYCAST) | Q(role=IPAddressRoleChoices.ROLE_VIP) | Q(role=IPAddressRoleChoices.ROLE_VRRP)):
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
