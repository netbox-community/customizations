#!/usr/bin/python3


from django.test import TestCase
import netaddr

from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Module,
    ModuleBay,
    ModuleType,
    Platform,
    Site,
)
from dcim.models.device_components import Interface

from scripts.common.errors import InvalidInput
import scripts.common.validators as validators


class ScriptTestCase(TestCase):
    fixtures = [
        "/opt/fixtures/templates.json",
    ]

    @classmethod
    def setUpTestData(cls):
        """Run once per TestCase instance."""
        edge = Device(
            name="edge-test",
            device_type=DeviceType.objects.get(model="QFX10008"),
            device_role=DeviceRole.objects.get(slug="edge-router"),
            platform=Platform.objects.get(slug="junos"),
            site=Site.objects.get(name="NET-META-ANY"),
        )
        edge.save()
        fpc0 = Module(
            device=edge,
            module_bay=ModuleBay.objects.get(device=edge, name="FPC0"),
            module_type=ModuleType.objects.get(model="QFX10000-30C"),
        )
        fpc0.save()

        edge_no_ifaces = Device(
            name="edge-no-ifaces",
            device_type=DeviceType.objects.get(model="QFX10008"),
            device_role=DeviceRole.objects.get(slug="edge-router"),
            platform=Platform.objects.get(slug="junos"),
            site=Site.objects.get(name="NET-META-ANY"),
        )
        edge_no_ifaces.save()

    ################################################################################
    #                        Validators for single values                          #
    ################################################################################

    def test_validate_IP(self):
        validators.validate_IP("test", "192.0.2.42")
        validators.validate_IP("test", "2001:db8:23::42")

        for ip in [
            "192.0.2.256",
            "192.0.2.24/23",
            "2001:db8::/64",
            "2001:db8:abcd:efgh",
        ]:
            with self.assertRaisesRegex(InvalidInput, "is not a valid IP address"):
                validators.validate_IP("test", ip)

    def test_validate_prefix(self):
        validators.validate_prefix("test", "192.0.2.42/23")
        validators.validate_prefix("test", "2001:db8:23::42/64")

        for pfx in [
            "192.0.2.256",
            "192.0.2.24",
            "192.0.2.24/33",
            "2001:db8:23::42",
            "2001:db8:abcd:efgh",
            "2001:db8::/129",
        ]:
            with self.assertRaisesRegex(InvalidInput, "is not a valid IP prefix!"):
                validators.validate_prefix("test", pfx)

    def test_validate_device_name(self):
        validators.validate_device_name("test", "edge-test")
        with self.assertRaisesRegex(
            InvalidInput,
            "Given device name .* does not exist!",
        ):
            validators.validate_device_name("test", "does-not-exist")

    def test_validate_VLAN_ID(self):
        validators.validate_VLAN_ID("test", 1)
        validators.validate_VLAN_ID("test", 42)
        validators.validate_VLAN_ID("test", 4096)

        for vid in ["abc", "-1", "0", "4097"]:
            with self.assertRaisesRegex(InvalidInput, "is not a valid VLAN ID"):
                validators.validate_VLAN_ID("test", vid)

    def test_validate_bool(self):
        validators.validate_bool("test", True)
        validators.validate_bool("test", False)

        with self.assertRaisesRegex(InvalidInput, "is not a valid boolean"):
            validators.validate_bool("test", None)
        with self.assertRaisesRegex(InvalidInput, "is not a valid boolean"):
            validators.validate_bool("test", "abc")
        with self.assertRaisesRegex(InvalidInput, "is not a valid boolean"):
            validators.validate_bool("test", 0)
        with self.assertRaisesRegex(InvalidInput, "is not a valid boolean"):
            validators.validate_bool("test", {})

    def test_validate_VLAN_ID(self):
        validators.validate_ASN("test", 1)
        validators.validate_ASN("test", 42)
        validators.validate_ASN("test", 4294967296)

        for asn in ["abc", "-1", "0", "4294967297"]:
            with self.assertRaisesRegex(InvalidInput, "is not a valid ASN"):
                validators.validate_ASN("test", asn)

    ################################################################################
    #                      Validators to be applied manually                       #
    ################################################################################

    def test_validate_IP_within_subnet(self):
        validators.validate_IP_within_subnet("192.2.0.42", "192.2.0.0/24")
        validators.validate_IP_within_subnet("2001:db8::42", "2001:db8::/64")
        validators.validate_IP_within_subnet(
            netaddr.IPNetwork("192.2.0.42/24"), netaddr.IPNetwork("192.2.0.0/24")
        )

        with self.assertRaisesRegex(InvalidInput, "Invalid prefix .*, no / present!"):
            validators.validate_IP_within_subnet("192.0.2.42", "192.0.0.0")

        with self.assertRaisesRegex(InvalidInput, "Failed to parse IP .* or prefix"):
            validators.validate_IP_within_subnet(
                "2001:db8::abcd:efgh", "2001:db8:23::/64"
            )

        with self.assertRaisesRegex(InvalidInput, "Failed to parse IP .* or prefix"):
            validators.validate_IP_within_subnet("192.0.2.42/25", "192.0.2.0/24")

        fail_subnet = {
            "192.0.2.42": "192.0.0.0/24",
            "2001:db8::42": "2001:db8:23::/64",
        }
        for ip, pfx in fail_subnet.items():
            with self.assertRaisesRegex(
                InvalidInput, "IP address .* does not belong to subnet"
            ):
                validators.validate_IP_within_subnet(ip, pfx)

    def test_validate_prefixes_within_same_subnet(self):
        validators.validate_prefixes_within_same_subnet(
            "192.0.2.23/24", "192.0.2.42/24"
        )
        validators.validate_prefixes_within_same_subnet(
            "2001:db8::23/64", "2001:db8::42/64"
        )

        fail_combinations = {
            "192.0.2.23/24": "192.0.2.42/33",
            "192.0.2.23/24": "192.0.2.42/25",
            "192.0.2.23/24": "192.0.3.42/24",
            "2001:db8:23::/64": "2001:db8:42::/64",
            "2001:db8::1/127": "2001:db8::2/127",
        }

        for ip1, ip2 in fail_combinations.items():
            with self.assertRaisesRegex(
                InvalidInput, "are not part of the same subnet"
            ):
                validators.validate_prefixes_within_same_subnet(ip1, ip2)

    def test_validate_device_interface(self):
        edge = Device.objects.get(name="edge-test")
        edge_et000 = Interface.objects.get(name="et-0/0/0")
        validators.validate_device_interface(edge, edge_et000)

        edge = Device.objects.get(name="edge-no-ifaces")

        with self.assertRaisesRegex(
            InvalidInput, "Interface .* does not belong to device"
        ):
            validators.validate_device_interface(edge, edge_et000)
