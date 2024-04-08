import re  # required for DeviceAssetTagValidator
from extras.validators import CustomValidator


# make sure active devices have tenants
class ActiveDeviceTenantValidator(CustomValidator):
    def validate(self, instance):
        if instance.status == "active" and not instance.tenant:
            self.fail("Active devices must have a tenant set!", field="tenant")


# make sure active devices have a custom field filled out
class DeviceCustomFieldsValidator(CustomValidator):
    def validate(self, instance):
        custom_field_name = "field_name"
        if instance.status == "active" and instance.asset_tag:
            if not instance.cf[custom_field_name]:
                self.fail(
                    f"Active device with an asset tags must have {custom_field_name} value set",
                    field=f"cf_{custom_field_name}",
                )


# make sure asset tags (if filled in) match regex format
class DeviceAssetTagValidator(CustomValidator):
    def validate(self, instance):
        if instance.asset_tag:
            pattern = re.compile("^(\d{5})$")
            if not pattern.match(instance.asset_tag):
                self.fail(
                    "Asset tag does not match Asset tag format", field="asset_tag"
                )
