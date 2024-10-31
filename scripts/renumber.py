"""
This script allows you to renumber a network: it renumbers all
Prefixes, IPAddresses and/or IPRanges within the given source block
to the target block.

BACKUP YOUR DATABASE BEFORE USING!
"""

from ipam.models import VRF, Prefix, IPAddress, IPRange
from extras.scripts import Script, ObjectVar, IPAddressWithMaskVar, BooleanVar
from utilities.exceptions import AbortScript

class Renumber(Script):
    class Meta:
        name = "Renumber"
        description = "Renumber Prefixes, IPAddresses and Ranges"
        scheduling_enabled = False
        commit_default = False

    vrf = ObjectVar(model=VRF, label="VRF", required=False)
    source = IPAddressWithMaskVar(label="Original IP address block", required=True)
    target = IPAddressWithMaskVar(label="Target IP address block", required=True)
    renumber_prefixes = BooleanVar(label="Renumber prefixes", default=True)
    renumber_ipaddresses = BooleanVar(label="Renumber IP Addresses", default=True)
    renumber_ipranges = BooleanVar(label="Renumber IP Ranges", default=True)

    def run(self, data, commit):
        vrf = data["vrf"]
        source = data["source"]
        target = data["target"]

        if source.version != target.version:
            raise AbortScript("Source and target IP address version do not match")

        if source.prefixlen != target.prefixlen:
            raise AbortScript("Source and target prefix lengths do not match")

        offset = target.value - source.value
        if not offset:
            raise AbortScript("Source and target prefixes must be different")

        action = False

        if data["renumber_prefixes"]:
            n = 0
            for o in Prefix.objects.filter(vrf=vrf, prefix__net_contained_or_equal=source):
                o.snapshot()
                was = f"{o}"
                o.prefix.value += offset
                o.full_clean()
                o.save()
                self.log_info(f"Prefix {was} -&gt; {o}")
                n += 1
            self.log_success(f"Renumbered {n} Prefixes")
            action = True

        if data["renumber_ipaddresses"]:
            n = 0
            for o in IPAddress.objects.filter(vrf=vrf, address__net_host_contained=source):
                o.snapshot()
                was = f"{o}"
                o.address.value += offset
                o.full_clean()
                o.save()
                self.log_info(f"IP Address {was} -&gt; {o}")
                n += 1
            self.log_success(f"Renumbered {n} IP Addresses")
            action = True

        if data["renumber_ipranges"]:
            n = 0
            for o in IPRange.objects.filter(vrf=vrf, start_address__net_host_contained=source, end_address__net_host_contained=source):
                o.snapshot()
                was = f"{o}"
                o.start_address.value += offset
                o.end_address.value += offset
                o.full_clean()
                o.save()
                self.log_info(f"IP Range {was} -&gt; {o}")
                n += 1
            self.log_success(f"Renumbered {n} IP Ranges")
            action = True

        if not action:
            self.log_info(f"No changes requested")
