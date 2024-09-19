"""
This script reports on power utilisation and power port availability,
either globally (aggregated per site), or for an individual site
(listing all the devices).

It's a script rather than a report so that it can prompt for site choice.

It doesn't rely on power ports being connected to power feeds or
calculations done at PDU level; it uses the allocated_draw of
each power port directly.
"""

import csv
import io
from dcim.choices import PowerPortTypeChoices
from dcim.models import Site, Device, PowerPort, PowerOutlet, PowerFeed, PowerPanel
from extras.scripts import Script, StringVar, ObjectVar, ChoiceVar

DC_TYPES = [PowerPortTypeChoices.TYPE_DC]

class PowerUsageAllSites(Script):
    class Meta:
        name = "Power Usage (all sites)"
        description = "Report on allocated power per site"
        scheduling_enabled = False
        commit_default = False

    def run(self, data, commit):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Site','Allocated Draw'])
        for site in Site.objects.filter(status='active'):
            power_ports = PowerPort.objects.filter(device__site=site,device__status='active')
            site_draw = sum(((pp.allocated_draw or 0) for pp in power_ports))
            if site_draw > 0:
                writer.writerow([site.name, site_draw])
        return output.getvalue()

class PowerUsageSingleSite(Script):
    class Meta:
        name = "Power Usage (single site)"
        description = "Report on allocated power for each device in a site"
        scheduling_enabled = False
        commit_default = False

    site = ObjectVar(
        model=Site,
        query_params={
            'status': 'active',
        },
        label="Site",
    )

    def run(self, data, commit):
        output = io.StringIO()
        writer = csv.writer(output)
        site = data['site']
        power_ports = PowerPort.objects.filter(device__site=site,device__status='active')
        writer.writerow(['Device','Port','Allocated Draw'])
        site_draw = 0
        for pp in power_ports:
            if not pp.allocated_draw:
                continue
            writer.writerow([pp.device.name, pp.name, pp.allocated_draw])
            site_draw += pp.allocated_draw
        self.log_success(f"Total allocated draw for {site}: {site_draw}W")
        return output.getvalue()

class PowerOutletsAllSites(Script):
    class Meta:
        name = "Power Outlets (all sites)"
        description = "Report on total/free power outlets per site"
        scheduling_enabled = False
        commit_default = False

    def run(self, data, commit):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Site','AC total','AC free','DC total','DC free'])
        for site in Site.objects.filter(status='active'):
            ac_total = ac_free = dc_total = dc_free = 0
            power_ports = PowerOutlet.objects.filter(device__site=site,device__status='active')
            for pp in power_ports:
                if pp.type in DC_TYPES:
                    dc_total += 1
                    dc_free += (0 if pp.mark_connected or pp.cable else 1)
                else:
                    ac_total += 1
                    ac_free += (0 if pp.mark_connected or pp.cable else 1)
            if dc_total > 0 or ac_total > 0:
                writer.writerow([site.name, ac_total, ac_free, dc_total, dc_free])
        return output.getvalue()

class PowerOutletsSingleSite(Script):
    class Meta:
        name = "Power Outlets (single site)"
        description = "Report on power outlets for each PDU in a site"
        scheduling_enabled = False
        commit_default = False

    site = ObjectVar(
        model=Site,
        query_params={
            'status': 'active',
        },
        label="Site",
    )

    def run(self, data, commit):
        output = io.StringIO()
        writer = csv.writer(output)
        site = data['site']
        devices = Device.objects.filter(site=site,status='active')
        writer.writerow(['Device','Outlet Type','Total','Free'])
        for device in devices:
            count_by_type = {}  # type => [total, free]
            for pp in device.poweroutlets.all():
                c = count_by_type.setdefault(pp.type, [0,0])
                c[0] += 1
                if not (pp.mark_connected or pp.cable):
                    c[1] += 1
            for type, vals in count_by_type.items():
                writer.writerow([device.name, type, vals[0], vals[1]])
        return output.getvalue()
