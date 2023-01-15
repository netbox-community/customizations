from extras.validators import CustomValidator
from circuits.models import Circuit


class SiteStatusCircuitValidator(CustomValidator):
    """Prevent sites from being retired if they have circuits that aren't in
    deprovisioning or decommissioned status."""

    def validate(self, site):
        circuit_count = (
            Circuit.objects.filter(terminations__site=site)
            .exclude(status__in=["deprovisioning", "decommissioned"])
            .count()
        )
        if site.status == "retired" and circuit_count > 0:
            self.fail(
                f"Site status cannot be set to 'retired', {circuit_count} circuits"
                "are not in deprovisioning or decommissioned status.",
                field="status",
            )
