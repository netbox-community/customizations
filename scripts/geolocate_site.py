# geolocate_site.py

# Make sure to add `geocoder` to your `local_requirements.txt` and make sure it is installed in your Python venv.

import geocoder
from dcim.models import Site, SiteGroup, Region
from extras.scripts import Script, ObjectVar, BooleanVar

name = "Populate geolocation for sites"


class SiteGeoAllRegion(Script):
    class Meta:
        name = "All sites for a region"
        description = "Retrieve list of all sites and populate the latitude/longitude fields based on their physical address."
        commit_default = True

    region = ObjectVar(model=Region)
    overwrite = BooleanVar(
        default=False,
        label="Override existing value",
        description="If location already exists, update the value.",
    )

    def run(self, data, commit):
        for site in get_sites_for_region(data["region"]):
            update_site(self, site)


class SiteGeoAllSiteGroup(Script):
    class Meta:
        name = "All sites for a site group"
        description = "Retrieve list of all sites and populate the latitude/longitude fields based on their physical address."
        commit_default = True

    group = ObjectVar(model=SiteGroup)
    overwrite = BooleanVar(
        default=False,
        label="Override existing value",
        description="If location already exists, update the value.",
    )

    def run(self, data, commit):
        for site in get_sites_for_group(data["group"]):
            update_site(self, site)


class SiteGeoOne(Script):
    class Meta:
        name = "Specific site"
        description = "Populate the latitude/longitude fields for a specific site based on its physical address."
        commit_default = True

    location = ObjectVar(model=Site)
    overwrite = BooleanVar(
        default=False,
        label="Override existing value",
        description="If location already exists, update the value.",
    )

    def run(self, data, commit):
        site = data["location"]
        update_site(self, site, data["overwrite"])


def update_site(script, site, overwrite=False):
    if site.physical_address:
        if site.latitude and site.longitude and overwrite == False:
            script.log_info(
                f"{site.name}: {site.physical_address} already at {site.longitude}, {site.latitude}"
            )
        elif g := geocoder.osm(site.physical_address):
            script.log_success(
                f"{site.name} geolocation found: {round(g.y,6)}, {round(g.x,6)}"
            )
            site.full_clean()
            site.latitude = round(g.y, 6)
            site.longitude = round(g.x, 6)
            site.save()
        else:
            script.log_failure(
                f"{site.name} no geolocation found for {site.physical_address}"
            )
    else:
        script.log_warning(f"No physical address for {site.name}")


def get_sites_for_region(region):
    region_list = [region]
    get_child_regions(region, region_list)
    site_list = []
    for place in region_list:
        site_list.extend(iter(Site.objects.filter(region=place)))
    return site_list


def get_child_regions(region, region_list):
    for sub_region in Region.objects.filter(parent=region):
        region_list.append(sub_region)
        get_child_regions(sub_region, region_list)
    return region_list


def get_sites_for_group(group):
    group_list = [group]
    get_child_groups(group, group_list)
    site_list = []
    for type in group_list:
        site_list.extend(iter(Site.objects.filter(group=type)))
    return site_list


def get_child_groups(group, group_list):
    for sub_group in SiteGroup.objects.filter(parent=group):
        group_list.append(sub_group)
        get_child_groups(sub_group, group_list)
    return group_list
