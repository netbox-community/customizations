from django.db.models import Count

from dcim.choices import SiteStatusChoices
from dcim.models import Site
from extras.reports import Report


class VirtualizationReport(Report):

    description = "Validate the network virtualization environment for a site"

    def test_cluster_exists(self):
        """
        Cluster exists for site.
        """

        sites = Site.objects.filter(status=SiteStatusChoices.STATUS_ACTIVE)
        missing_clusters = Site.objects.filter(clusters__isnull=True).exclude(
            tags__name__in=["no-cluster"]
        )

        for site in sites:
            if site in missing_clusters:
                self.log_failure(site, "Missing VM cluster")

            else:
                self.log_success(site)

    def test_vms_exist(self):
        """
        Correct number of VMs (account for special tag or not)
        """

        sites = (
            Site.objects.filter(status__in=[1, 2])
            .prefetch_related("tags")
            .annotate(vm_count=Count("clusters__virtual_machines"))
            .order_by("name")
        )

        for site in sites:
            tags = site.tags.names()
            desired_count = 2
            special_tag = ""
            if "special_tag" in [tag for tag in tags]:
                desired_count = 3
                special_tag = " special_tag"  # Prefix space is for log printing

            if not site.vm_count:
                self.log_failure(
                    site, "No VMs ({}/{})".format(site.vm_count, desired_count)
                )
            elif site.vm_count == desired_count:
                self.log_success(site)

            elif site.vm_count > desired_count:
                self.log_warning(
                    site, "Too many VMs ({}/{})".format(site.vm_count, desired_count)
                )
            elif site.vm_count < desired_count:
                self.log_warning(
                    site,
                    "Too few VMs ({}/{}){}".format(
                        site.vm_count, desired_count, special_tag
                    ),
                )
            else:
                self.log_info(site, "Unknown status")
