# site_address.py
# Make sure to add `geocoder` to your `local_requirements.txt` and make sure it is installed in your Python venv.
import geocoder
from dcim.models import Site
from extras.reports import Report


class checkSiteAddress(Report):
    description = "Check if site has a physical address and/or geolocation information"

    def test_site_address(self):
        for site in Site.objects.all():
            if site.physical_address:
                self.log_success(site)
            else:
                self.log_failure(site, site.name)

    def test_site_geo(self):
        for site in Site.objects.all():
            if site.latitude and site.longitude:
                self.log_success(site)
            else:
                if site.physical_address:
                    g = geocoder.osm(site.physical_address)
                    if g:
                        self.log_warning(
                            site,
                            f"Missing geo location - possible ({round(g.x,6)}, {round(g.y,6)})",
                        )
                    else:
                        self.log_warning(
                            site,
                            f"Missing geo location ({site.latitude}, {site.longitude})",
                        )
                else:
                    self.log_failure(
                        site,
                        f"Missing geo location ({site.latitude}, {site.longitude})",
                    )
