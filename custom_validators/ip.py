from extras.validators import CustomValidator

# created by Pieter Lambrecht
# make sure RFC1918 ips have a vrf assigned
class RequireVRFforRFC1918(CustomValidator):
    """Enforce a VRF for all RFC1918 ip space."""

    def validate(self, instance):
        _RFC1918 = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        if not instance.vrf:
            if instance.__class__.__module__ == "ipam.models.ip":
                try:
                    new_ip_address = ipaddress.ip_address(str(instance).split("/")[0])
                except ValueError as e:
                    raise self.fail(
                        f"Invalid IP address {instance}. Error {str(e)}", field="status"
                    )
                for ip_network in _RFC1918:
                    if new_ip_address in ipaddress.ip_network(ip_network):
                        self.fail("Private IP space requires a VRF!", field="status")

            if instance.__class__.__module__ == "ipam.models.prefix":
                try:
                    new_ip_network = ipaddress.ip_network(instance)
                except ValueError as e:
                    raise self.fail(
                        f"Invalid IP network {instance}. Error {str(e)}", field="status"
                    )
                for ip_network in _RFC1918:
                    if new_ip_network >= ipaddress.ip_network(ip_network):
                        self.fail("Private IP space requires a VRF!", field="status")
