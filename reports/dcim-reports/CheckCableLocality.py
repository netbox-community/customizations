from extras.reports import Report
from dcim.models import Cable, RearPort
from dcim.choices import CableTypeChoices

CABLE_TYPES_OK_BETWEEN_RACKS = {
    CableTypeChoices.TYPE_DAC_PASSIVE,
}

class CheckCableLocality(Report):
    description = "Warn on cables between racks, error on cables between sites"

    def test_cable_endpoints(self):
        for cable in Cable.objects.prefetch_related('termination_a','termination_b').all():
            if not getattr(cable.termination_a, 'device', None) or not getattr(cable.termination_b, 'device', None):
                continue
            if cable.termination_a.device.site != cable.termination_b.device.site:
                self.log_failure(cable, "Endpoints in different sites: {} ({}) and {} ({})".format(
                    cable.termination_a.device, cable.termination_a.device.site,
                    cable.termination_b.device, cable.termination_b.device.site,
                ))
                continue
            if isinstance(cable.termination_a, RearPort) and isinstance(cable.termination_b, RearPort):
                self.log_success(cable)
                continue
            if cable.termination_a.device.rack != cable.termination_b.device.rack and cable.type not in CABLE_TYPES_OK_BETWEEN_RACKS:
                self.log_warning(cable, "Endpoints in different racks: {} ({}) and {} ({})".format(
                    cable.termination_a.device, cable.termination_a.device.rack,
                    cable.termination_b.device, cable.termination_b.device.rack,
                ))
                continue
            self.log_success(cable)
