from django.db.models import Count, Q

from dcim.choices import SiteStatusChoices
from dcim.models import Site
from extras.reports import Report


class MplsCircuitReport(Report):
    """
    When you have multiple circuits at a site, but only one should have
    the 'mpls' tag.
    """

    description = "Check that each site only has one circuit tagged MPLS."

    def test_site_mpls_counts(self):

        site_circuit_counts = (
            Site.objects.filter(status=SiteStatusChoices.STATUS_ACTIVE)
            .annotate(
                mpls_count=Count(
                    "circuit_terminations",
                    filter=Q(circuit_terminations__circuit__tags__name__in=["mpls"]),
                )
            )
            .order_by("name")
        )

        for site in site_circuit_counts:
            if site.mpls_count > 1:

                self.log_failure(
                    site,
                    "{} circuits tagged MPLS, Reason: More than 1".format(
                        site.mpls_count
                    ),
                )

            elif not site.mpls_count:
                self.log_failure(site, "Reason: No circuits tagged MPLS")

            else:
                self.log_success(site)


class CircuitCountReport(Report):
    """
    Useful for cases where you have a standardized-ish number of
    circuits supposed to be attached to a site.
    """

    description = "Validate number of (non-decommissioned) circuits attached to a site."

    def test_site_circuits(self):

        site_circuit_counts = (
            Site.objects.filter(
                # We need circuits matching criteria and also
                # sites that have no circuits attached
                Q(
                    circuit_terminations__term_side="A",
                    # Only non-decommissioned circuits
                    circuit_terminations__circuit__status__in=[1, 2, 3, 4],
                )
                | Q(circuit_terminations__isnull=True),
                status=SiteStatusChoices.STATUS_ACTIVE,
            )
            .annotate(circuit_count=Count("circuit_terminations"))
            .order_by("name")
        )

        for site in site_circuit_counts:
            if site.circuit_count < 3:
                self.log_failure(
                    site, "{} circuit(s), Reason: 3 minimum".format(site.circuit_count)
                )

            elif site.circuit_count >= 7:
                self.log_failure(
                    site,
                    "{} circuit(s), Reason: 7 or more circuits!".format(
                        site.circuit_count
                    ),
                )

            elif site.circuit_count > 4:
                self.log_warning(
                    site,
                    "{} circuit(s), Reason: More than 4".format(site.circuit_count),
                )

            else:
                self.log_success(site.circuit_count)
