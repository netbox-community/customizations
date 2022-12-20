from dcim.models import Device, DeviceType, Site
from extras.reports import Report


class DeviceReport(Report):

    description = "Check device case insensitive name"

    @property
    def name(self):
        return "Device Name Report"

    def test_case_insensitive_name(self):
        devices = Device.objects.all()
        for device in devices:
            if device.name is not None:
                repeated_devices = []
                if device.tenant is not None:
                    repeated_devices = devices.filter(
                        name__iexact=device.name,
                        site_id=device.site.id,
                        tenant_id=device.tenant.id,
                    ).exclude(id=device.id)
                else:
                    repeated_devices = devices.filter(
                        name__iexact=device.name, site_id=device.site.id
                    ).exclude(id=device.id)

                for repeated_device in repeated_devices:
                    self.log_failure(
                        device,
                        f"Device with repeated name (case insensitive) [{repeated_device}]({repeated_device.get_absolute_url()})",
                    )

