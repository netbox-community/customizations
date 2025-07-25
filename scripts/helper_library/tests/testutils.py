#!/usr/bin/python3

"""Utils for setting up test data in the DB."""

from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Platform,
    Site,
)


def create_device(
    name: str, model: str, devrole_slug: str, site_name: str, platform_slug: str = None
) -> Device:
    """Create"""
    if platform_slug:
        dev = Device(
            name=name,
            device_type=DeviceType.objects.get(model=model),
            device_role=DeviceRole.objects.get(slug=devrole_slug),
            site=Site.objects.get(name=site_name),
            platform=Platform.objects.get(slug=platform_slug),
        )
    else:
        dev = Device(
            name=name,
            device_type=DeviceType.objects.get(model=model),
            device_role=DeviceRole.objects.get(slug=devrole_slug),
            site=Site.objects.get(name=site_name),
        )

    dev.save()

    return dev
