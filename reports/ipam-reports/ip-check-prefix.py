from ipam.choices import IPAddressRoleChoices
from ipam.models import IPAddress, Prefix
from extras.reports import Report

LOOPBACK_ROLES = [
    IPAddressRoleChoices.ROLE_LOOPBACK,
    IPAddressRoleChoices.ROLE_ANYCAST,
    IPAddressRoleChoices.ROLE_VIP,
    IPAddressRoleChoices.ROLE_VRRP,
]

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
            # We allow loopback-like things to be single address *or* have the parent prefix length
            if ipaddr.role in LOOPBACK_ROLES and a.size == 1:
                self.log_success(ipaddr)
                continue
            parents = [p for p in prefixes if
                              (p.vrf and p.vrf.id) == (ipaddr.vrf and ipaddr.vrf.id) and
                               p.prefix.version == a.version and a.ip in p.prefix]
            if not parents:
                self.log_info(ipaddr, "No parent prefix")
                continue
            parent = parents[-1]
            # If parent is a pool, allow single address *or* have the parent prefix length
            if parent.is_pool and a.size == 1:
                self.log_success(ipaddr)
                continue
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
