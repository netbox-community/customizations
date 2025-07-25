#!/usr/bin/python3
#
# Maximilian Wilhelm <max@sdn.clinic>
#  --  Thu 27 Jul 2023 05:38:01 PM CEST
#

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
import netaddr
import uuid

from circuits.choices import CircuitStatusChoices
from circuits.models import Circuit, CircuitType, Provider
from dcim.choices import InterfaceTypeChoices, LinkStatusChoices
from dcim.models import (
    ConsolePort,
    ConsoleServerPort,
    Device,
    Module,
    ModuleBay,
    ModuleType,
    FrontPort,
    RearPort,
    Platform,
    Site,
)
from dcim.models.device_components import Interface
from extras.choices import CustomFieldTypeChoices
from extras.models import CustomField, Tag
from extras.scripts import Script
from ipam.choices import PrefixStatusChoices
from ipam.models import VRF, IPAddress, Prefix, Role
from netbox.settings import VERSION
from tenancy.models import Tenant
from utilities.choices import ColorChoices
from scripts.common.constants import (
    CIRCUIT_TYPE_SLUG_DARK_FIBER,
    DEVICE_ROLE_SLUG_CS,
    DEVICE_ROLE_SLUG_EDGE_ROUTER,
    PLATFORM_SLUG_EOS,
    PLATFORM_SLUG_JUNOS,
    PREFIX_ROLE_SLUG_LOOPBACK_IPS,
    PREFIX_ROLE_SLUG_SITE_LOCAL,
    PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
)
from scripts.common.errors import InvalidInput, NetBoxDataError
import scripts.common.utils as utils
import scripts.tests.testutils as testutils

SINGLE_CABLE_ENDPOINT = [int(n) for n in VERSION.split("-")[0].split(".")] < [3, 3, 0]
DEVICE_ROLE_SLUG_PE = "pe"


def setup_customfields() -> None:
    # "pop" custom field on Prefixes
    # This uses an integer value to simulate a relationship to the PK of a NetBox plugin
    # holding information about all the POPs we have in our network.
    pfx_pop = CustomField(
        name="pop",
        type=CustomFieldTypeChoices.TYPE_INTEGER,
    )
    pfx_pop.save()
    pfx_pop.content_types.set([ContentType.objects.get_for_model(Prefix)])

    # "gateway_ip" custom field on IPAddresses
    gateway_ip = CustomField(
        name="gateway_ip",
        type=CustomFieldTypeChoices.TYPE_TEXT,
    )
    gateway_ip.save()
    gateway_ip.content_types.set([ContentType.objects.get_for_model(IPAddress)])


def setup_topology() -> None:
    """Set up test topology.

    Site: DC02

        Create a PE pe-test in Site DC02 using a Mellanox SN2010 device,
        iface Ethernet19 is put into lag1.

        Create patch panel pp-pe, where PE ifaces Ethernet1 is connected
        to front ports 1 of the panel.

    Site DC01

        Create edge-test in Site DC01 using Junper QFX10008 model and adds a
        QFX10000-30C Module into FPC0 slot.

        Create pp-DC01 with no front/rear ports connected.
    """

    # Set up pe-test + pp-pe + cabling
    pe = testutils.create_device("pe-test", "SN2010", DEVICE_ROLE_SLUG_PE, "DC02")
    pe_eth19 = utils.get_interface(pe, "Ethernet19")
    utils.get_or_create_LAG_interface_with_members(pe, "ae0", [pe_eth19])

    pp_cr = testutils.create_device("pp-pe", "24-port LC/LC PP", "patch-panel", "DC02")
    pp_cr.save()
    utils.connect_ports(
        Interface.objects.get(device=pe, name="Ethernet1"),
        FrontPort.objects.get(device=pp_cr, name="1"),
    )

    # Set up edge-test + fpc0 module
    edge = testutils.create_device(
        "edge-test",
        "QFX10008",
        DEVICE_ROLE_SLUG_EDGE_ROUTER,
        "DC01",
        PLATFORM_SLUG_JUNOS,
    )
    fpc0 = Module(
        device=edge,
        module_bay=ModuleBay.objects.get(device=edge, name="FPC0"),
        module_type=ModuleType.objects.get(model="QFX10000-30C"),
    )
    fpc0.save()
    edge_et_000 = utils.get_interface(edge, "et-0/0/0")
    utils.get_or_create_LAG_interface_with_members(edge, "ae0", [edge_et_000])

    # Set up connection between edge and PE
    utils.connect_ports(pe_eth19, edge_et_000)

    peer = testutils.create_device("Peer", "NET-META-Peer", "peer", "NET-META-ANY")
    peer.save()


def setup_ipam() -> None:
    """Set up IPAM data base line"""
    test_net_1 = Prefix(
        prefix="192.2.0.0/24",
        description="TEST-NET-1",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        is_pool=False,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_SITE_LOCAL),
        custom_field_data={"pop": 2342},
    )
    test_net_1.save()
    pop_tag = Tag(name="NET:PFX:PE_LOOPBACKS:test-a")
    pop_tag.save()
    test_net_1.tags.add(pop_tag)
    test_net_1.save()

    test_net_2 = Prefix(
        prefix="198.51.100.0/24",
        description="TEST-NET-2",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        is_pool=False,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_SITE_LOCAL),
    )
    test_net_2.save()

    ipv6_pfx = Prefix(
        prefix="2001:db8:2342::/48",
        description="IPv6 Site-local",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        is_pool=False,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_SITE_LOCAL),
        custom_field_data={"pop": 2342},
    )
    ipv6_pfx.save()

    pe_lo = Prefix(
        prefix="2001:db8:2342:ffff::/64",
        description="PE Loopback IPs - pad01",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_LOOPBACK_IPS),
        is_pool=True,
        custom_field_data={"pop": 2342},
    )
    pe_lo.save()

    pe_lo_non_pool = Prefix(
        prefix="192.168.0.0/31",
        description="PE Loopback IPs - v4 tiny",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_LOOPBACK_IPS),
        is_pool=False,
        custom_field_data={"pop": 2342},
    )
    pe_lo_non_pool.save()

    xfer = Prefix(
        prefix="100.64.0.0/24",
        status=PrefixStatusChoices.STATUS_CONTAINER,
        role=Role.objects.get(slug=PREFIX_ROLE_SLUG_TRANSFER_NETWORK),
        is_pool=False,
    )
    xfer.save()


class ScriptTestCase(TestCase):
    fixtures = [
        "/opt/fixtures/templates.json",
    ]

    @classmethod
    def setUpTestData(cls):
        """Run once per TestCase instance."""
        # Create console server (to have ConsoleServerPort(s))
        cs = testutils.create_device("cs-test", "ISR4331", DEVICE_ROLE_SLUG_CS, "DC01")
        nim = Module(
            device=cs,
            module_bay=ModuleBay.objects.get(device=cs, name="0/1"),
            module_type=ModuleType.objects.get(model="NIM-24A"),
        )
        nim.save()

        vrf = VRF(
            id=1,
            name="VRF1",
        )
        vrf.save()

        setup_customfields()
        setup_topology()
        setup_ipam()

    ################################################################################
    #                              Generic wrappers                                #
    ################################################################################

    def test_get_port_type(self):
        self.assertEqual(
            utils._get_port_type(ConsolePort.objects.all()[0]), "Console Port"
        )
        self.assertEqual(
            utils._get_port_type(ConsoleServerPort.objects.all()[0]),
            "Console Server Port",
        )
        self.assertEqual(utils._get_port_type(Interface.objects.all()[0]), "Interface")
        self.assertEqual(utils._get_port_type(FrontPort.objects.all()[0]), "Front Port")
        self.assertEqual(utils._get_port_type(RearPort.objects.all()[0]), "Rear Port")
        self.assertEqual(utils._get_port_type("foo"), "unknown")

    ################################################################################
    #                      Circuit related helper functions                        #
    ################################################################################

    def test_terminate_circuit_at_site(self):
        c = Circuit(
            cid=uuid.uuid4(),
            provider=Provider.objects.get(name="Provider1"),
            type=CircuitType.objects.get(slug=CIRCUIT_TYPE_SLUG_DARK_FIBER),
            status=CircuitStatusChoices.STATUS_ACTIVE,
        )
        c.save()

        # Circuit ends are unterminated by default
        self.assertIsNone(
            c.termination_a,
            "A-End termination of newly created circuit should be None!",
        )
        self.assertIsNone(
            c.termination_z,
            "Z-End termination of newly created circuit should be None!",
        )

        site_net_meta_any = Site.objects.get(name="NET-META-ANY")
        utils.terminate_circuit_at_site(c, site_net_meta_any, True)
        self.assertEqual(
            site_net_meta_any,
            c.termination_a.site,
            "A-End termination not at NET-META-ANY!",
        )

        site_lax_dc01 = Site.objects.get(name="DC01")
        utils.terminate_circuit_at_site(c, site_lax_dc01, False)
        self.assertEqual(
            site_lax_dc01,
            c.termination_z.site,
            "Z-End termination not at DC01!",
        )

    def test_connect_circuit_termination_to_port(self):
        circuit = Circuit(
            cid=uuid.uuid4(),
            provider=Provider.objects.get(name="Provider1"),
            type=CircuitType.objects.get(slug=CIRCUIT_TYPE_SLUG_DARK_FIBER),
            status=CircuitStatusChoices.STATUS_ACTIVE,
        )
        circuit.save()

        # Terminate both ends of the Circuit
        site_net_meta_any = Site.objects.get(name="NET-META-ANY")
        ct_a = utils.terminate_circuit_at_site(circuit, site_net_meta_any, True)

        site_lax_dc02 = Site.objects.get(name="DC02")
        ct_b = utils.terminate_circuit_at_site(circuit, site_lax_dc02, False)

        peer = Device.objects.get(name="Peer")
        peer_iface = Interface(
            device=peer, name="test1", type=InterfaceTypeChoices.TYPE_100GE_QSFP28
        )
        peer_iface.save()
        if SINGLE_CABLE_ENDPOINT:
            self.assertIsNone(
                peer_iface.connected_endpoint,
                msg="Expected newly created Peer interface to be unconnected.",
            )
        else:
            self.assertIsNone(
                peer_iface.connected_endpoints[0],
                msg="Expected newly created Peer interface to be unconnected.",
            )

        # Connect A-End
        cable_a = utils.connect_circuit_termination_to_port(ct_a, peer_iface, False)
        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(
                cable_a.termination_a,
                ct_a,
                msg="Expected cable A-End to be connected to ct_a",
            )
            self.assertEqual(
                cable_a.termination_b,
                peer_iface,
                msg="Expected cable B-End to be connected to peer iface",
            )
        else:
            self.assertEqual(
                cable_a.a_terminations[0],
                ct_a,
                msg="Expected cable A-End to be connected to ct_a",
            )
            self.assertEqual(
                cable_a.b_terminations[0],
                peer_iface,
                msg="Expected cable B-End to be connected to peer iface",
            )
        self.assertEqual(
            cable_a.status,
            LinkStatusChoices.STATUS_CONNECTED,
            msg="Cable should be connected, but isn't",
        )

        # Try to connect B-End to already connected port
        try:
            utils.connect_circuit_termination_to_port(ct_b, peer_iface, True)
            self.fail(
                "Connecting B-End of circuit to already connected port should fail"
            )
        except InvalidInput as i:
            pass

        # Try to re-connect A-End
        try:
            peer_iface2 = Interface(
                device=peer, name="test2", type=InterfaceTypeChoices.TYPE_100GE_QSFP28
            )
            peer_iface2.save()
            utils.connect_circuit_termination_to_port(ct_a, peer_iface2, True)
            self.fail("Connecting already connected A-End of circuit should fail.")
        except InvalidInput as i:
            pass

        # Connect B-End to panel rear port
        pp = Device.objects.get(name="pp-pe")
        pp_rp = RearPort.objects.get(
            device=pp,
            name="24",
        )
        cable_b = utils.connect_circuit_termination_to_port(ct_b, pp_rp, True)
        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(
                cable_b.termination_a,
                ct_b,
                msg="Expected cable A-End to be connected to ct_b",
            )
            self.assertEqual(
                cable_b.termination_b,
                pp_rp,
                msg="Expected cable B-End to be connected to PP Rear Port",
            )
        else:
            self.assertEqual(
                cable_b.a_terminations[0],
                ct_b,
                msg="Expected cable A-End to be connected to ct_b",
            )
            self.assertEqual(
                cable_b.b_termination[0],
                pp_rp,
                msg="Expected cable B-End to be connected to PP Rear Port",
            )
        self.assertEqual(
            cable_b.status,
            LinkStatusChoices.STATUS_PLANNED,
            msg="Cable should be planned, but isn't",
        )

    def test_connect_ports(self):
        pe = Device.objects.get(name="pe-test")
        pp = Device.objects.get(name="pp-pe")

        pe_eth5 = Interface.objects.get(device=pe, name="Ethernet5")
        pp_fp5 = FrontPort.objects.get(device=pp, name="5")

        self.assertIsNone(pe_eth5._link_peer, msg="PE Interface already connected")
        self.assertIsNone(pp_fp5._link_peer, msg="Panel Front Port already connected")

        cable = utils.connect_ports(pe_eth5, pp_fp5, True)

        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(cable.termination_a, pe_eth5)
            self.assertEqual(cable.termination_b, pp_fp5)
        else:
            self.assertEqual(cable.a_terminations[0], pe_eth5)
            self.assertEqual(cable.b_terminations[0], pp_fp5)

        self.assertEqual(cable.status, LinkStatusChoices.STATUS_PLANNED)
        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(pe_eth5._link_peer, pp_fp5)
            self.assertEqual(pp_fp5._link_peer, pe_eth5)
        else:
            self.assertEqual(pe_eth5.link_peers[0], pp_fp5)
            self.assertEqual(pp_fp5.link_peers[0], pe_eth5)

        # Re-creation of the same cable should be no-op, yielding the existing cable
        cable2 = utils.connect_ports(pe_eth5, pp_fp5, True)
        self.assertEqual(cable, cable2)

        # Try to connect the already connected PE interface (port_a)
        pp_fp6 = FrontPort.objects.get(device=pp, name="6")
        try:
            cable = utils.connect_ports(pe_eth5, pp_fp6, True)
            self.fail(
                "Sholdn't be able to create a cable to an already connected port_a"
            )
        except InvalidInput:
            pass

        # Try to connect the alreay connected panel Front Port (port_b)
        pe_eth6 = Interface.objects.get(device=pe, name="Ethernet6")
        try:
            cable = utils.connect_ports(pe_eth6, pp_fp5, True)
            self.fail(
                "Sholdn't be able to create a cable to an already connected port_b"
            )
        except InvalidInput:
            pass

    def test_remove_existing_cable_if_exists(self):
        pe = Device.objects.get(name="pe-test")
        pp = Device.objects.get(name="pp-pe")

        pe_eth5 = Interface.objects.get(device=pe, name="Ethernet5")
        pp_fp5 = FrontPort.objects.get(device=pp, name="5")

        if SINGLE_CABLE_ENDPOINT:
            self.assertIsNone(pe_eth5._link_peer, msg="PE Interface already connected")
            self.assertIsNone(
                pp_fp5._link_peer, msg="Panel Front Port already connected"
            )
        else:
            self.assertIsNone(
                pe_eth5.link_peers[0], msg="PE Interface already connected"
            )
            self.assertIsNone(
                pp_fp5.link_peers[0], msg="Panel Front Port already connected"
            )

        iface = utils.remove_existing_cable_if_exists(pe_eth5)
        self.assertEqual(pe_eth5, iface)

        utils.connect_ports(pe_eth5, pp_fp5, True)
        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(pe_eth5._link_peer, pp_fp5)
        else:
            self.assertEqual(pe_eth5.link_peers[0], pp_fp5)

        iface = utils.remove_existing_cable_if_exists(pe_eth5)
        if SINGLE_CABLE_ENDPOINT:
            self.assertEqual(iface._link_peer, None)
        else:
            self.assertEqual(iface.link_peers[0], None)
        self.assertEqual(pe_eth5, iface)

    def test_get_other_cable_end_string(self):
        pe = Device.objects.get(name="pe-test")
        pp = Device.objects.get(name="pp-pe")

        pe_eth5 = Interface.objects.get(device=pe, name="Ethernet5")
        pp_fp5 = FrontPort.objects.get(device=pp, name="5")

        cable = utils.connect_ports(pe_eth5, pp_fp5, True)

        pp_fp5_str_actual = utils.get_other_cable_end_string(cable, pe_eth5)
        pp_fp5_str_expected = utils.get_port_string(pp_fp5)
        self.assertEqual(pp_fp5_str_expected, pp_fp5_str_actual)

        pe_eth5_str_actual = utils.get_other_cable_end_string(cable, pp_fp5)
        pe_eth5_str_expected = utils.get_port_string(pe_eth5)
        self.assertEqual(pe_eth5_str_expected, pe_eth5_str_actual)

        pp_fp6 = FrontPort.objects.get(device=pp, name="6")
        try:
            utils.get_other_cable_end_string(cable, pp_fp6)
            self.fail("get_other_cable_end_string with invalid port should fail")
        except NetBoxDataError:
            pass

    ################################################################################
    #                       Device related helper functions                        #
    ################################################################################

    def test_get_device(self):
        self.assertIsNotNone(utils.get_device("pe-test"))
        self.assertIsNone(utils.get_device("does-not-exist"))

    def test_get_device_platform_slug(self):
        pe = Device.objects.get(name="pe-test")
        edge = Device.objects.get(name="edge-test")

        self.assertEqual(PLATFORM_SLUG_JUNOS, utils.get_device_platform_slug(edge))
        self.assertIsNone(utils.get_device_platform_slug(pe))

    def test_set_device_platform_slug(self):
        pe = Device.objects.get(name="pe-test")
        edge = Device.objects.get(name="edge-test")

        script = Script()
        utils.set_device_platform(edge, PLATFORM_SLUG_JUNOS, script=script)
        self.assertEqual(PLATFORM_SLUG_JUNOS, utils.get_device_platform_slug(edge))
        self.assertEqual(
            f"Device {edge.name} already has platform (slug) {PLATFORM_SLUG_JUNOS} set.",
            script.log[0][1],
        )

        script = Script()
        utils.set_device_platform(pe, PLATFORM_SLUG_EOS, script=script)
        self.assertEqual(PLATFORM_SLUG_EOS, utils.get_device_platform_slug(pe))
        self.assertEqual(
            f"Set platform (slug) {PLATFORM_SLUG_EOS} to device {pe.name}",
            script.log[0][1],
        )

        with self.assertRaisesRegex(InvalidInput, "Platform .* does not exist!"):
            utils.set_device_platform(
                edge, "somEtherneting-somEtherneting-does-not-exit"
            )

    def test_get_device_max_VRF_count(self):
        pe = utils.get_device("pe-test")

        # No tag by default
        with self.assertRaises(
            NetBoxDataError,
            msg=f"Should have raise NetBoxDataError!",
        ):
            utils.get_device_max_VRF_count(pe)

        tag, _ = utils.get_or_create_tag("NET:MaxVRFCount=123")
        pe.device_type.tags.add(tag)
        pe.device_type.save()
        self.assertEqual(123, utils.get_device_max_VRF_count(pe))

    ################################################################################
    #                     Interface related helper functions                       #
    ################################################################################

    def test_get_port_string(self):
        iface = Interface.objects.all()[0]
        port_desc_actual = utils.get_port_string(iface)
        port_desc_expected = f"Interface {iface.name} on {iface.device.name}"
        self.assertEqual(port_desc_actual, port_desc_expected)

    def test_get_remote_interface(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth19 = Interface.objects.get(device=pe, name="Ethernet19")
        pe_ae0 = Interface.objects.get(device=pe, name="ae0")

        edge = Device.objects.get(name="edge-test")
        edge_et000 = Interface.objects.get(device=edge, name="et-0/0/0")
        edge_ae0 = Interface.objects.get(device=edge, name="ae0")

        # PE/Ethernet19 is connected to edge/et-0/0/0, both are part of respective ae0
        self.assertEqual(edge_et000, utils.get_remote_interface_native(pe_eth19))
        self.assertEqual(pe_eth19, utils.get_remote_interface_native(edge_et000))

        self.assertEqual(edge_ae0, utils.get_remote_interface(pe_ae0))
        self.assertEqual(pe_ae0, utils.get_remote_interface(edge_ae0))

        # Empty LAG
        ae1, _ = utils.get_or_create_LAG_interface_with_members(pe, "ae1", [])
        self.assertIsNone(utils.get_remote_interface(ae1))

        # Add unconnected Ethernet1 to the LAG
        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")
        ae1, _ = utils.get_or_create_LAG_interface_with_members(pe, "ae1", [pe_eth1])
        self.assertIsNone(utils.get_remote_interface(pe_eth1))

    def test_get_interface(self):
        pe = Device.objects.get(name="pe-test")

        self.assertIsNotNone(utils.get_interface(pe, "Ethernet1"))
        self.assertIsNone(utils.get_interface(pe, "does-not-exist"))

    def test_interface_types_compatible(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")

        for iface_type in [
            InterfaceTypeChoices.TYPE_25GE_SFP28,
            InterfaceTypeChoices.TYPE_10GE_SFP_PLUS,
            InterfaceTypeChoices.TYPE_10GE_X2,
            InterfaceTypeChoices.TYPE_10GE_XENPAK,
            InterfaceTypeChoices.TYPE_10GE_XFP,
        ]:
            self.assertTrue(utils.interface_types_compatible(pe_eth1, iface_type))

        self.assertFalse(
            utils.interface_types_compatible(
                pe_eth1, InterfaceTypeChoices.TYPE_100GE_QSFP28
            )
        )

        pe_eth19 = Interface.objects.get(device=pe, name="Ethernet19")
        self.assertFalse(
            utils.interface_types_compatible(
                pe_eth19, InterfaceTypeChoices.TYPE_10GE_SFP_PLUS
            )
        )

    # Implicitly tests create_interface()
    def test_get_or_create_interface(self):
        pe = Device.objects.get(name="pe-test")

        pe_eth1, created = utils.get_or_create_interface(
            pe, "Ethernet1", InterfaceTypeChoices.TYPE_25GE_SFP28
        )
        self.assertIsNotNone(pe_eth1)
        self.assertFalse(created)

        new_iface, created = utils.get_or_create_interface(
            pe, "new-iface", InterfaceTypeChoices.TYPE_100GE_QSFP28, "foo"
        )
        self.assertIsNotNone(new_iface)
        self.assertTrue(created)
        self.assertEqual(new_iface.type, InterfaceTypeChoices.TYPE_100GE_QSFP28)
        self.assertEqual(new_iface.description, "foo")

    # Also tests get_LAG_members()
    def test_get_or_create_LAG_interface_with_members(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth19 = utils.get_interface(pe, "Ethernet19")
        pe_ae0 = utils.get_interface(pe, "ae0")

        self.assertListEqual([pe_eth19], utils.get_LAG_members(pe_ae0))

        # "Ethernet1" is already part of "ae0"
        with self.assertRaisesRegex(
            NetBoxDataError, "should be placed in LAG .*, but is member of LAG"
        ):
            lag = utils.get_or_create_LAG_interface_with_members(
                pe, "lag1", [pe_eth19], "bar"
            )

        # No-op, everything is already in place
        lag, created = utils.get_or_create_LAG_interface_with_members(
            pe, "ae0", [pe_eth19], "bar"
        )
        self.assertEqual(pe_ae0, lag)
        self.assertFalse(created)
        self.assertEqual(InterfaceTypeChoices.TYPE_LAG, lag.type)
        self.assertEqual(lag, pe_eth19.lag)
        self.assertListEqual([pe_eth19], utils.get_LAG_members(pe_ae0))

        # Add interface to existing LAG
        pe_eth2 = utils.get_interface(pe, "Ethernet2")
        lag, created = utils.get_or_create_LAG_interface_with_members(
            pe, "ae0", [pe_eth2], "bar"
        )
        self.assertEqual(pe_ae0, lag)
        self.assertFalse(created)
        self.assertEqual(InterfaceTypeChoices.TYPE_LAG, lag.type)
        self.assertEqual(lag, pe_eth19.lag)
        self.assertEqual(lag, pe_eth2.lag)
        self.assertListEqual([pe_eth2, pe_eth19], utils.get_LAG_members(pe_ae0))

    def test_create_next_available_LAG_interface(self):
        pe = Device.objects.get(name="pe-test")

        # Only ae0 exists
        next_lag = utils.create_next_available_LAG_interface(
            pe, "new LAG", override_basename="ae"
        )
        self.assertEqual("ae1", next_lag.name)
        self.assertEqual(InterfaceTypeChoices.TYPE_LAG, next_lag.type)
        self.assertEqual("new LAG", next_lag.description)

        # ae0, ae1, and ae3 exist
        pe_ae3 = Interface(device=pe, name="ae3", type=InterfaceTypeChoices.TYPE_LAG)
        pe_ae3.save()
        next_lag = utils.create_next_available_LAG_interface(
            pe, "new LAG", override_basename="ae"
        )
        self.assertEqual("ae2", next_lag.name)

        # ae0 exists
        edge = Device.objects.get(name="edge-test")
        next_lag = utils.create_next_available_LAG_interface(
            edge,
            start_at=200,
            # Figure out lag_basename automagically
        )
        self.assertEqual("ae200", next_lag.name)
        self.assertEqual(InterfaceTypeChoices.TYPE_LAG, next_lag.type)
        self.assertEqual("", next_lag.description)

        # Not an integer
        with self.assertRaisesRegex(
            InvalidInput, "Invalid value for 'start_at' paramter, not an integer"
        ):
            utils.create_next_available_LAG_interface(edge, start_at={})

        # int < 0
        with self.assertRaisesRegex(
            InvalidInput, "Invalid value for 'start_at' paramter, needs to be > 0"
        ):
            utils.create_next_available_LAG_interface(edge, start_at=-1)

        # Unknown platform
        plat = Platform(name="something-something", slug="something-something")
        plat.save()
        pe.platform = plat
        pe.save()
        with self.assertRaisesRegex(
            NetBoxDataError,
            "No LAG base config found for platform .* nor manufacturer .*!",
        ):
            utils.create_next_available_LAG_interface(pe)

    # Tests create_vlan_unit() + get_child_interfaces()
    def test_units_and_child_interface(self):
        pe = Device.objects.get(name="pe-test")
        pe_test1 = Interface.objects.get(device=pe, name="Ethernet1")

        vlan42 = utils.get_interface(pe, "Ethernet1.42")
        self.assertIsNone(vlan42)

        vlan42 = utils.create_vlan_unit(pe_test1, 42)
        self.assertIsNotNone(vlan42)
        self.assertEqual("Ethernet1.42", vlan42.name)
        self.assertEqual(pe_test1, vlan42.parent)
        self.assertEqual(InterfaceTypeChoices.TYPE_VIRTUAL, vlan42.type)

        with self.assertRaisesRegex(InvalidInput, "VLAN ID .* already configured"):
            vlan42 = utils.create_vlan_unit(pe_test1, 42)

        children = utils.get_child_interfaces(pe_test1)
        self.assertListEqual([vlan42], children)

    def test_tag_interfaces(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")
        pe_eth2 = Interface.objects.get(device=pe, name="Ethernet2")

        self.assertEqual(0, len(pe_eth1.tags.all()))

        # Tagging with an non-existing tag should fail
        try:
            utils.tag_interfaces([pe_eth1, pe_eth2], "Test Tag")
            self.fail("Tagging interface with non-existing tag should fail")
        except NetBoxDataError:
            pass

        # Create tag and tag interfaces
        tag = Tag(name="Test Tag", slug="test-tag")
        tag.save()

        utils.tag_interfaces([pe_eth1, pe_eth2], "Test Tag")

        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")
        pe_eth2 = Interface.objects.get(device=pe, name="Ethernet2")

        self.assertTrue(tag in pe_eth1.tags.all() and len(pe_eth1.tags.all()) == 1)
        self.assertTrue(tag in pe_eth2.tags.all() and len(pe_eth2.tags.all()) == 1)

    def test_assign_IP_address_to_interface(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")

        # There should be 0 IPs configured
        ips = IPAddress.objects.filter(interface=pe_eth1)
        self.assertEqual(0, len(ips))

        # Assign one IP
        utils.assign_IP_address_to_interface(pe_eth1, "192.0.2.42/31", None)
        ips = IPAddress.objects.filter(interface=pe_eth1)
        self.assertEqual(1, len(ips))
        self.assertEqual("192.0.2.42/31", str(ips[0]))

        # Assign the same IP again, which should be a no-op
        utils.assign_IP_address_to_interface(pe_eth1, "192.0.2.42/31", None)
        ips = IPAddress.objects.filter(interface=pe_eth1)
        self.assertEqual(1, len(ips))
        self.assertEqual("192.0.2.42/31", str(ips[0]))
        self.assertEqual({}, ips[0].custom_field_data)

        # Validate custom field handling
        pe_test2 = Interface.objects.get(device=pe, name="Ethernet2")
        # There should be 0 IPs configured
        ips = IPAddress.objects.filter(interface=pe_test2)
        self.assertEqual(0, len(ips))

        cf_data = {
            "gateway_ip": "192.0.2.22",
        }
        utils.assign_IP_address_to_interface(pe_test2, "192.0.2.23/31", cf_data)
        ips = IPAddress.objects.filter(interface=pe_test2)
        self.assertEqual(1, len(ips))
        self.assertEqual("192.0.2.23/31", str(ips[0]))
        self.assertEqual(cf_data, ips[0].custom_field_data)

    ################################################################################
    #                       IPAM related helper functions                          #
    ################################################################################

    def test_get_prefixes(self):
        test_net_1 = Prefix.objects.get(prefix="192.2.0.0/24")
        test_net_2 = Prefix.objects.get(prefix="198.51.100.0/24")
        ipv6_pfx = Prefix.objects.get(prefix="2001:db8:2342::/48")

        self.assertEqual(
            [],
            utils.get_prefixes(
                PREFIX_ROLE_SLUG_SITE_LOCAL, utils.AF_IPv6, custom_fields={"pop": 123}
            ),
        )

        pfxs_v4 = utils.get_prefixes(PREFIX_ROLE_SLUG_SITE_LOCAL, utils.AF_IPv4)
        self.assertEqual([test_net_1, test_net_2], pfxs_v4)

        pfxs_v6 = utils.get_prefixes(PREFIX_ROLE_SLUG_SITE_LOCAL, utils.AF_IPv6)
        self.assertEqual([ipv6_pfx], pfxs_v6)

        # Explicitly check with is_container set
        pfxs = utils.get_prefixes(
            PREFIX_ROLE_SLUG_SITE_LOCAL, utils.AF_IPv4, is_container=True
        )
        self.assertEqual([test_net_1, test_net_2], pfxs)

        # w/ Tag
        pfxs = utils.get_prefixes(
            PREFIX_ROLE_SLUG_SITE_LOCAL,
            utils.AF_IPv4,
            is_container=True,
            tag_name="NET:PFX:PE_LOOPBACKS:test-a",
        )
        self.assertEqual([test_net_1], pfxs)

        # w/ CF
        pfxs = utils.get_prefixes(
            PREFIX_ROLE_SLUG_SITE_LOCAL,
            utils.AF_IPv4,
            is_container=True,
            custom_fields={"pop": 2342},
        )
        self.assertEqual([test_net_1], pfxs)

        # w/ CF & tag
        pfxs = utils.get_prefixes(
            PREFIX_ROLE_SLUG_SITE_LOCAL,
            utils.AF_IPv4,
            is_container=True,
            custom_fields={"pop": 2342},
            tag_name="NET:PFX:PE_LOOPBACKS:test-a",
        )
        self.assertEqual([test_net_1], pfxs)

    # Also test get_prefix_role()
    # TODO: Check side-effects (warning logs)
    def test_get_or_create_prefix(self):
        self.assertIsNone(utils.get_prefix_role("foo"))

        role = Role(name="Test Role", slug="test-role")
        role.save()

        r = utils.get_prefix_role("test-role")
        self.assertEqual(role, r)

        # Make sure prefix doesn't exist
        ip_network = netaddr.ip.IPNetwork("192.0.2.0/24")
        self.assertEqual(0, len(Prefix.objects.filter(prefix=ip_network)))

        # Create Prefix with Role, from str
        pfx, created = utils.get_or_create_prefix("192.0.2.0/24", "Test Prefix", role)
        self.assertTrue(created)
        self.assertEqual(ip_network, pfx.prefix)
        self.assertEqual("Test Prefix", pfx.description)
        self.assertEqual(role, pfx.role)

        # Try to re-create the same prefix
        pfx, created = utils.get_or_create_prefix("192.0.2.0/24", "Test Prefix", role)
        self.assertFalse(created)
        self.assertEqual(ip_network, pfx.prefix)
        self.assertEqual("Test Prefix", pfx.description)
        self.assertEqual(role, pfx.role)

        # Create 2nd prefix without Role, from IPNetwork obj
        ip_network = netaddr.ip.IPNetwork("192.0.2.0/25")
        self.assertEqual(0, len(Prefix.objects.filter(prefix=ip_network)))
        pfx, created = utils.get_or_create_prefix(
            ip_network,
            "Test Prefix #2",
        )
        self.assertTrue(created)
        self.assertEqual(ip_network, pfx.prefix)
        self.assertEqual("Test Prefix #2", pfx.description)
        self.assertEqual(None, pfx.role)

    def test_get_or_create_prefix_from_ip(self):
        ip_obj = IPAddress(address="192.0.2.0/31")
        ip_obj.save()

        role = Role(name="Test Role", slug="test-role")
        role.save()

        # Create prefix from IP with Role
        pfx, created = utils.get_or_create_prefix_from_ip(
            ip_obj, "IP from IPAddress", role
        )
        self.assertTrue(created)
        self.assertEqual(netaddr.ip.IPNetwork("192.0.2.0/31"), pfx.prefix)
        self.assertEqual("IP from IPAddress", pfx.description)
        self.assertEqual(role, pfx.role)

        # Create Prefix from IPNetwork (already exists)
        pfx, created = utils.get_or_create_prefix_from_ip(
            netaddr.ip.IPNetwork("192.0.2.1/31"), "IP from IPNetwork", role
        )
        self.assertFalse(created)
        self.assertEqual(netaddr.ip.IPNetwork("192.0.2.0/31"), pfx.prefix)
        self.assertEqual("IP from IPAddress", pfx.description)
        self.assertEqual(role, pfx.role)

        # Create Prefix from IP str
        pfx, created = utils.get_or_create_prefix_from_ip(
            "192.0.2.2/31",
            "IP from str",
        )
        self.assertTrue(created)
        self.assertEqual(netaddr.ip.IPNetwork("192.0.2.2/31"), pfx.prefix)
        self.assertEqual("IP from str", pfx.description)
        self.assertEqual(None, pfx.role)

    # test get_interface_IPs() + get_interface_IP()
    def test_get_interface_IPs(self):
        pe = Device.objects.get(name="pe-test")
        pe_eth1 = Interface.objects.get(device=pe, name="Ethernet1")

        # There should be 0 IPs configured
        ips = IPAddress.objects.filter(interface=pe_eth1)
        self.assertEqual(0, len(ips))

        # Assign one IP
        utils.assign_IP_address_to_interface(pe_eth1, "192.0.2.42/31", None)

        ips = utils.get_interface_IPs(pe_eth1)
        self.assertEqual(1, len(ips))
        self.assertEqual("192.0.2.42/31", str(ips[0]))

        ip = utils.get_interface_IP(pe_eth1, "192.0.2.42/31")
        self.assertEqual("192.0.2.42/31", str(ip))

        ip = utils.get_interface_IP(pe_eth1, "192.0.2.23/31")
        self.assertIsNone(ip)

    def test_get_next_free_IP_from_pools(self):
        self.assertIsNone(utils.get_next_free_IP_from_pools([]))

        pe_lo_pools = utils.get_prefixes(
            PREFIX_ROLE_SLUG_LOOPBACK_IPS,
            utils.AF_IPv6,
            is_container=True,
            custom_fields={"pop": 2342},
        )

        # Regular v6 pool
        ip_v6_0 = utils.get_next_free_IP_from_pools(pe_lo_pools)
        self.assertIsNotNone(ip_v6_0)
        self.assertEqual("2001:db8:2342:ffff::/128", str(ip_v6_0))

        ip_v6_1 = utils.get_next_free_IP_from_pools(pe_lo_pools)
        self.assertIsNotNone(ip_v6_1)
        self.assertEqual("2001:db8:2342:ffff::1/128", str(ip_v6_1))

        # Small v4 pool to check edge cases
        v4_pool = utils.get_prefixes(
            PREFIX_ROLE_SLUG_LOOPBACK_IPS,
            utils.AF_IPv4,
            is_container=True,
            custom_fields={"pop": 2342},
        )

        ip_v4_0 = utils.get_next_free_IP_from_pools(v4_pool)
        self.assertIsNotNone(ip_v4_0)
        self.assertEqual("192.168.0.0/32", str(ip_v4_0))

        ip_v4_1 = utils.get_next_free_IP_from_pools(v4_pool)
        self.assertIsNotNone(ip_v6_1)
        self.assertEqual("192.168.0.1/32", str(ip_v4_1))

        self.assertIsNone(utils.get_next_free_IP_from_pools(v4_pool))

    def test_get_next_free_prefix_from_prefixes(self):
        with self.assertRaisesRegex(InvalidInput, "Prefix role .* does not exist"):
            utils.get_next_free_prefix_from_prefixes(
                [],
                18,
                "Some fancy description",
                "Non-existing prefix role",
            )

        test_net_1 = Prefix.objects.get(prefix="192.2.0.0/24")
        test_net_2 = Prefix.objects.get(prefix="198.51.100.0/24")
        containers = [test_net_1, test_net_2]

        new_pfx_26 = utils.get_next_free_prefix_from_prefixes(
            containers,
            26,
            "Slash Twentysix",
            PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
            is_pool=False,
        )
        self.assertIsNotNone(new_pfx_26)
        self.assertEqual("192.2.0.0/26", str(new_pfx_26))
        self.assertEqual("Slash Twentysix", new_pfx_26.description)
        self.assertEqual(26, new_pfx_26.mask_length)
        self.assertEqual(PREFIX_ROLE_SLUG_TRANSFER_NETWORK, new_pfx_26.role.slug)

        new_pfx_25 = utils.get_next_free_prefix_from_prefixes(
            containers,
            25,
            "Slash Twentyfive",
            is_pool=True,
            custom_fields={"pop": 2342},
        )
        self.assertIsNotNone(new_pfx_25)
        self.assertEqual("192.2.0.128/25", str(new_pfx_25))
        self.assertEqual("Slash Twentyfive", new_pfx_25.description)
        self.assertEqual(25, new_pfx_25.mask_length)
        self.assertIsNone(new_pfx_25.role)
        self.assertEqual(2342, new_pfx_25.custom_field_data["pop"])

        new_pfx_24 = utils.get_next_free_prefix_from_prefixes(
            containers,
            24,
            "Slash Twentyfour",
        )
        self.assertIsNone(new_pfx_24)

    def test_get_next_free_prefix_from_container_fail(self):
        with self.assertRaisesRegex(InvalidInput, "Prefix role .* does not exist"):
            utils.get_next_free_prefix_from_container(
                "does-not-exist",
                utils.AF_IPv4,
                18,
                "Too big too not fail",
            )

        with self.assertRaisesRegex(InvalidInput, "No container prefix found for role"):
            utils.get_next_free_prefix_from_container(
                PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
                utils.AF_IPv6,
                127,
                "No site-locals",
            )

        # container exists, but not w/ tag
        with self.assertRaisesRegex(
            InvalidInput, "No container prefix found for role .* and tag"
        ):
            utils.get_next_free_prefix_from_container(
                PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
                utils.AF_IPv4,
                31,
                "No site-locals",
                container_tag_name="does-not-exist",
            )

        # container exists, but not w/ tag & CF
        with self.assertRaisesRegex(
            InvalidInput,
            "No container prefix found for role .* and tag .* and custom fields",
        ):
            utils.get_next_free_prefix_from_container(
                PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
                utils.AF_IPv4,
                31,
                "No site-locals",
                container_tag_name="does-not-exist",
                container_custom_fields={"pop": 123},
            )

        with self.assertRaisesRegex(InvalidInput, "Prefix role .* does not exist"):
            utils.get_next_free_prefix_from_container(
                PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
                utils.AF_IPv4,
                31,
                "No site-locals",
                prefix_role_slug="does-not-exist",
            )

        # Requesting a /17 from a /18 should fail
        with self.assertRaisesRegex(NetBoxDataError, "but no free prefix available"):
            utils.get_next_free_prefix_from_container(
                PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
                utils.AF_IPv4,
                17,
                "Too big too not fail",
            )

    def test_get_next_free_prefix_from_container_OK(self):
        new_pfx_26 = utils.get_next_free_prefix_from_container(
            PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
            utils.AF_IPv4,
            26,
            "Fancy new Prefix",
            is_pool=True,
        )
        self.assertEqual(26, new_pfx_26.mask_length)
        self.assertEqual("Fancy new Prefix", new_pfx_26.description)
        self.assertTrue(new_pfx_26.is_pool)
        self.assertEqual("100.64.0.0/26", str(new_pfx_26))

        # Requesting a /25 should skip 100.64.0.64/26 and lead to 100.64.0.128/25
        new_pfx_25 = utils.get_next_free_prefix_from_container(
            PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
            utils.AF_IPv4,
            25,
            "Slash Twentyfive",
        )
        self.assertEqual(25, new_pfx_25.mask_length)
        self.assertEqual("Slash Twentyfive", new_pfx_25.description)
        self.assertFalse(new_pfx_25.is_pool)
        self.assertEqual("100.64.0.128/25", str(new_pfx_25))

        # Requesting /31 transfer-network from container w/ tag
        site_local_pfx = utils.get_next_free_prefix_from_container(
            PREFIX_ROLE_SLUG_SITE_LOCAL,
            utils.AF_IPv4,
            31,
            "Thirtyone",
            container_tag_name="NET:PFX:PE_LOOPBACKS:test-a",
            is_pool=False,
            prefix_role_slug=PREFIX_ROLE_SLUG_TRANSFER_NETWORK,
        )
        self.assertEqual("192.2.0.0/31", str(site_local_pfx))
        self.assertEqual(PREFIX_ROLE_SLUG_TRANSFER_NETWORK, site_local_pfx.role.slug)

    def test_get_IPs_from_IPSet(self):
        self.assertEqual(
            [
                netaddr.IPNetwork("2001:db8:2342:FE00::/127"),
                netaddr.IPNetwork("2001:db8:2342:FE00::1/127"),
            ],
            utils.get_IPs_from_IPSet(netaddr.IPSet(["2001:db8:2342:FE00::/127"]), 127),
        )

        self.assertEqual(
            [netaddr.IPNetwork("192.0.2.0/31"), netaddr.IPNetwork("192.0.2.1/31")],
            utils.get_IPs_from_IPSet(netaddr.IPSet(["192.0.2.0/31"]), 31),
        )

    ################################################################################
    #                        Tag related helper functions                          #
    ################################################################################

    def test_get_tag(self):
        tag = utils.get_tag("Test Tag")
        self.assertIsNone(tag)

        # Create tag and tag interfaces
        t = Tag(name="Test Tag", slug="test-tag")
        t.save()

        tag = utils.get_tag("Test Tag")
        self.assertEqual(t, tag)

    def test_get_or_create_tag(self):
        self.assertIsNone(utils.get_tag("Test Tag"))

        tag, created = utils.get_or_create_tag("Test Tag", ColorChoices.COLOR_PURPLE)
        self.assertTrue(created)
        self.assertEqual("Test Tag", tag.name)
        self.assertEqual(ColorChoices.COLOR_PURPLE, tag.color)

        tag, created = utils.get_or_create_tag("Test Tag", ColorChoices.COLOR_PURPLE)
        self.assertFalse(created)
        self.assertEqual("Test Tag", tag.name)
        self.assertEqual(ColorChoices.COLOR_PURPLE, tag.color)
