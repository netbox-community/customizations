from extras.reports import Report
from dcim.models import Cable, RearPort
from dcim.choices import CableTypeChoices

CABLE_TYPES_OK_BETWEEN_RACKS = {
    CableTypeChoices.TYPE_DAC_PASSIVE,
}

class CheckCableLocality(Report):
    description = "Warn on cables between racks, error on cables between sites"

    def test_cable_endpoints(self):
        for cable in Cable.objects.prefetch_related('terminations').all():
            devices = set()
            term_types = set()
            sites = set()
            racks = set()
            for t in cable.terminations.all():
                device = getattr(t.termination, 'device', None)
                if not device:
                    continue
                devices.add(device)
                term_types.add(t.termination_type.name)
                if device.site:
                    sites.add(device.site)
                if device.rack:
                    racks.add(device.rack)

            if len(sites) == 0:
                continue
            if len(sites) > 1:
                self.log_failure(cable, f"Endpoints in different sites: {sites} {devices} {cable.type}")
                continue
            # Rearport to rearport connections are expected to be in different racks
            if len(term_types) == 1 and "rear port" in term_types:
                self.log_success(cable)
                continue
            if len(racks) > 1 and cable.type not in CABLE_TYPES_OK_BETWEEN_RACKS:
                self.log_warning(cable, f"Endpoints in different racks: {racks} {devices} {cable.type}")
                continue
            self.log_success(cable)
