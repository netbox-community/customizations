#!/usr/bin/python3

"""NetBox scripts utils library."""

import re
from typing import Literal, Optional, Union

import netaddr.ip
from circuits.models import Circuit, CircuitTermination
from dcim.choices import InterfaceTypeChoices, LinkStatusChoices
from dcim.models import (
    Cable,
    ConsolePort,
    ConsoleServerPort,
    Device,
    FrontPort,
    Platform,
    RearPort,
    Site,
)
from dcim.models.device_components import Interface
from extras.models import Tag
from extras.scripts import Script
from ipam.choices import PrefixStatusChoices
from ipam.models import VRF, IPAddress, Prefix, Role
from netaddr import IPNetwork, IPSet
from netbox.settings import VERSION
from scripts.common.constants import (
    MANUFACTURER_TO_LAG_BASENAME_MAP,
    PLATFORM_TO_LAG_BASENAME_MAP,
)
from scripts.common.errors import InvalidInput, NetBoxDataError
from utilities.choices import ColorChoices

SINGLE_CABLE_ENDPOINT = [int(n) for n in VERSION.split("-")[0].split(".")] < [3, 3, 0]

NET_MaxVRFCount_Tag_re = re.compile(r"^NET:MaxVRFCount=(\d+)$")
INTERFACE_TYPE_COMPATIBILITY = {
    # <interface type>: [list of port speeds which can be connected]
    "25gbase-x-sfp28": [
        "10gbase-x-sfpp",
        "10gbase-x-xfp",
        "10gbase-x-xenpak",
        "10gbase-x-x2",
    ],
}
DEVICE__NAME_RE = re.compile(r"^([a-z]+\d+)\.([a-z]+\d+)$")

AF_IPv4 = 4
AF_IPv6 = 6

################################################################################
#                              Generic wrappers                                #
################################################################################


def log_maybe(script: Script, level: str, msg: str) -> None:
    """Log the given msg with the given level if the 'script' is not None."""
    if script is None:
        return

    func_name = f"log_{level}"
    if not hasattr(script, func_name):
        raise Exception("Invalid log level!")

    func = getattr(script, func_name)
    func(msg)


def _get_port_type(
    port: Union[ConsolePort, ConsoleServerPort, Interface, FrontPort, RearPort]
) -> str:
    if isinstance(port, ConsolePort):
        return "Console Port"

    if isinstance(port, ConsoleServerPort):
        return "Console Server Port"

    if isinstance(port, Interface):
        return "Interface"

    if isinstance(port, FrontPort):
        return "Front Port"

    if isinstance(port, RearPort):
        return "Rear Port"

    return "unknown"


################################################################################
#                      Circuit related helper functions                        #
################################################################################


def terminate_circuit_at_site(
    circuit: Circuit,
    site: Site,
    a_end: bool,
    script: Optional[Script] = None,
) -> CircuitTermination:
    """Terminate the given Circuit at the given Site.

    Parameters
    ----------
    circuit : Circuit
        The Circuit to terminate at the given Site.
    site : Site
        Site to create the CircuitTerminate at.
    a_end: bool
        True is A-End should be terminate at the given Site, False for Z-End.
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    CircuitTermination
        Return a circuit.CircuitTermination object.
    """
    if a_end:
        termination = circuit.termination_a
    else:
        termination = circuit.termination_z

    # Does circuit already have a termination?
    if termination is not None:
        if termination.site == site:
            log_maybe(
                script,
                "info",
                f"Circuit {str(circuit)} already terminating at site {site.name}",
            )
            return termination

        raise InvalidInput(
            f"Circuit {str(circuit)} already terminated at site {str(termination.site)},"
            f"but should land at site {site.name}"
        )

    term_side = "A" if a_end else "Z"
    ct = CircuitTermination(
        circuit=circuit,
        term_side=term_side,
        site=site
        # xconnect_id
        # pp_info
    )
    ct.save()

    log_maybe(
        script,
        "success",
        f"Terminated {term_side} end of circuit {str(circuit)} at site {site.name}",
    )

    return ct


def connect_circuit_termination_to_port(
    ct: CircuitTermination,
    port: Union[Interface, FrontPort, RearPort],
    planned: bool = False,
    script: Optional[Script] = None,
) -> Cable:
    """Connect the given CircuitTermination to the given port.

    Parameters
    ----------
    ct : CircuitTermination
        The CircuitTermination to connect to a port.
    port : Union[Interface, FrontPort, RearPort]
        Port to connect CircuitTerminat to.
    planned: bool, optional
        True if the cable should have status Planned, False for Connected (default False)
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Cable
        Return a dcim.models.Cable object.
    """
    port_type = _get_port_type(port)

    if ct.cable is not None:
        msg = f"{ct} of circuit {ct.circuit} already connected!"
        log_maybe(script, "failure", msg)
        raise InvalidInput(msg)

    if port._link_peer is not None:
        msg = (
            f"Error while connecting {ct.circuit} to {port_type} {port.name}"
            f"on device {port.device.name}: {port_type} already connected!"
        )
        log_maybe(script, "failure", msg)
        raise InvalidInput(msg)

    status = LinkStatusChoices.STATUS_CONNECTED
    if planned:
        status = LinkStatusChoices.STATUS_PLANNED
    if SINGLE_CABLE_ENDPOINT:
        c = Cable(status=status, termination_a=ct, termination_b=port)
    else:
        c = Cable(status=status, a_terminations=[ct], b_terminations=[port])
    c.save()

    log_maybe(
        script,
        "success",
        f"Connected circuit {ct.circuit} {ct} to {port_type} {port} on {port.device.name}",
    )

    return c


################################################################################
#                      Cabling related helper functions                        #
################################################################################


def connect_ports(
    port_a: Union[Interface, FrontPort, RearPort],
    port_b: Union[Interface, FrontPort, RearPort],
    planned: bool = False,
    script: Optional[Script] = None,
) -> Cable:
    """Connect the given ports via a direct Cable.

    If the two ports are already connected to each other, the function will create a log entry
    (if script is given) and return. If any of the two ports is connected to something else,
    this will raise an InvalidInput Exception.

    Parameters
    ----------
    port_a : Union[Interface, FrontPort, RearPort]
        A-End of cable.
    port_b : Union[Interface, FrontPort, RearPort]
        Z-End of cable.
    planned: bool, optional
        True if the cable should have status Planned, False for Connected (default False)
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Cable
        Return a dcim.models.Cable object.
    """
    port_desc_a = get_port_string(port_a)
    port_desc_b = get_port_string(port_b)

    if port_a._link_peer is not None or port_a._link_peer is not None:
        if port_a._link_peer == port_b:
            log_maybe(
                script,
                "info",
                f"{port_desc_a} and {port_desc_b} already connected",
            )
            return port_a.cable

        msg = f"{port_desc_a} already connected to something else!"
        log_maybe(script, "failure", msg)
        raise InvalidInput(msg)

    if port_b._link_peer is not None or port_b._link_peer is not None:
        msg = f"{port_desc_b} already connected to something else!"
        log_maybe(script, "failure", msg)
        raise InvalidInput(msg)

    status = LinkStatusChoices.STATUS_CONNECTED
    if planned:
        status = LinkStatusChoices.STATUS_PLANNED

    if SINGLE_CABLE_ENDPOINT:
        c = Cable(status=status, termination_a=port_a, termination_b=port_b)
    else:
        c = Cable(status=status, a_terminations=[port_a], b_terminations=[port_b])
    c.save()

    log_maybe(
        script,
        "success",
        f"Connected {port_desc_a} and {port_desc_b} with a cable",
    )

    return c


def remove_existing_cable_if_exists(
    iface: Interface, script: Optional[Script] = None
) -> Interface:
    """If there is an existing cable terminating at iface remove the cable and re-fetch the Interface and return it.

    If there is not cable attached, just return the Interface.

    Parameters
    ----------
    iface : Interface
        The Interface to remove a connected cable from, if any
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Interface
        The unchanged Interface if not cable is connected, or the newly fetched Interface from the DB
    """
    if iface._link_peer is None:
        log_maybe(
            script,
            "info",
            f"No cable connected to interface {iface.name} on {iface.device}",
        )
        return iface

    cable = iface.cable
    remote = get_other_cable_end_string(cable, iface)
    log_maybe(
        script,
        "warning",
        f"Removed cable on interface {iface.name} on {iface.device} connected to {remote}",
    )

    cable.delete()

    return Interface.objects.get(pk=iface.pk)


def get_other_cable_end_string(
    cable: Cable, port: Union[Interface, FrontPort, RearPort]
) -> str:
    """Return the remote end of the given cable / interface as a string (for logging).

    Parameters
    ----------
    cable : Cable
        The cable at hand.
    port : Union[Interface, FrontPort, RearPort]
        The local port.

    Returns
    -------
    str
        Port description of the remote end.
    """
    if SINGLE_CABLE_ENDPOINT:
        if port == cable.termination_a:
            return get_port_string(cable.termination_b)

        elif port == cable.termination_b:
            return get_port_string(cable.termination_a)
    else:
        if port == cable.termination_a[0]:
            return get_port_string(cable.b_terminations[0])

        elif port == cable.termination_b[0]:
            return get_port_string(cable.a_terminations[0])

    port_desc = get_port_string(port)
    raise NetBoxDataError(f"Given cable not connected to {port_desc}")


################################################################################
#                       Device related helper functions                        #
################################################################################


def get_device(device_name: str) -> Optional[Device]:
    """Get a device from the DB.

    This will return None if the device does not exist.

    Parameters
    ----------
    device_name : str
        The name of the Device to look for.

    Returns
    -------
    Device or None
        Return a dcim.models.Device object.
    """
    try:
        return Device.objects.get(name=device_name)
    except Device.DoesNotExist:
        return None


def get_device_platform_slug(device: Device) -> Optional[str]:
    """Get a device's platform (slug).

    Parameters
    ----------
    device: dcim.models.Device
        The device object to get the platform slug from.

    Returns
    -------
    str, optional
        Return the platform slug string, or None if no platform is set.
    """
    if device.platform is None:
        return None

    return device.platform.slug


def set_device_platform(
    device: Device, platform_slug: str, script: Optional[Script] = None
) -> None:
    """Set the given Platform to the given device.

    Parameters
    ----------
    device: dcim.models.Device
        The device object to set the platform on.
    platform_slug: str
        The slug of the Platform to set on the device.
    script: Script, optional
        Script object this function is called from, used for logigng.
    """
    try:
        plat = Platform.objects.get(slug=platform_slug)
    except Platform.DoesNotExist:
        raise InvalidInput(f"Platform (slug) {platform_slug} does not exist!")

    if device.platform == plat:
        log_maybe(
            script,
            "info",
            f"Device {device.name} already has platform (slug) {platform_slug} set.",
        )
        return

    device.platform = plat
    device.save()

    log_maybe(
        script,
        "success",
        f"Set platform (slug) {platform_slug} to device {device.name}",
    )


def get_device_lag_base_cfg(device: Device) -> tuple[str, int]:
    """Get the LAG basename of the given device, e.g. 'ae' or 'Port-Channel'.

    This will raise an NetBoxDataError if neither for the device's platform (if any)
    nor for the device's manufacturer a LAG basename config is defined.

    Parameters
    ----------
    device: dcim.models.Device
        The device to get the LAG basename for.

    Returns
    -------
    str:
        The basename for LAG interfaces.
    int:
        The minimum LAG number.
    """
    platform_slug = get_device_platform_slug(device)
    if platform_slug:
        lag_basename_cfg = PLATFORM_TO_LAG_BASENAME_MAP.get(platform_slug)
        if lag_basename_cfg is not None:
            return lag_basename_cfg

    manufacturer_slug = device.device_type.manufacturer.slug
    lag_basename_cfg = MANUFACTURER_TO_LAG_BASENAME_MAP.get(manufacturer_slug)
    if lag_basename_cfg is None:
        raise NetBoxDataError(
            f"No LAG base config found for platform (slug) {platform_slug} "
            f"nor manufacturer (slug) {manufacturer_slug}!"
        )

    return lag_basename_cfg


def get_device_max_VRF_count(device: Device) -> int:
    """Get the maximum number of VRFs possible on the given device.

    Some devices / device types, we can only have a fixed number of VRFs.
    This is indicated by tagging the device type with "NET:MaxVRFCount=<value>".

    If no maximum VRF information is stored for the device type of the given device,
    this will raise a NetBoxDataError Exception.

    Parameters
    ----------
    device : Device
        A dcim.models.Device object.

    Returns
    -------
    int
        The number of VRFs supported on the device.
    """
    device_type = device.device_type

    max_VRFs = 0
    for tag in device_type.tags.all():
        match = NET_MaxVRFCount_Tag_re.match(tag.name)
        if not match:
            continue

        if max_VRFs != 0:
            raise NetBoxDataError(
                f"Found multiple values for NET:MaxVRFCount tag: {max_VRFs} vs. {match.group(1)}!"
            )
        max_VRFs = int(match.group(1))

    if max_VRFs == 0:
        raise NetBoxDataError(
            f"Can't figure out how many VRFs devices of type {device_type} support - dying of shame."
        )

    return max_VRFs


################################################################################
#                     Interface related helper functions                       #
################################################################################


def get_port_string(
    port: Union[ConsolePort, ConsoleServerPort, Interface, FrontPort, RearPort]
) -> str:
    """Get the description of the given port.

    Parameters
    ----------
    port : Union[ConsolePort, ConsoleServerPort, Interface, FrontPort, RearPort]
        Any kind of port object.

    Returns
    -------
    str
        The printable port string
    """
    port_type = _get_port_type(port)
    return f"{port_type} {port} on {port.device.name}"


def get_remote_interface(iface: Interface) -> Optional[Interface]:
    """Get the remote interface the given interface is connected to (if any).

    If the given iface is a LAG, it will return the remote LAG interface (if any),
    None, if no member interfaces exist or all of them are unconnected.  It will
    raise a NetBoxDataError, if LAG members are connected to different remote
    devices, are part of different LAGs on the remote device, or the remote
    interfaces aren't part of a LAG at all.

    Parameters
    ----------
    iface : Interface
        The Interface to trace from.

    Returns
    -------
    Interface or None
        Return a dcim.models.device_components.Interface object, or None.
    """
    if iface.is_lag:
        return get_remote_interface_LAG(iface)

    return get_remote_interface_native(iface)


def get_remote_interface_native(iface: Interface) -> Optional[Interface]:
    """Get the remote interface the given phyiscal Interface if connected to.

    Parameters
    ----------
    iface : Interface
        The Interface to trace from.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object, or None.
    """
    if SINGLE_CABLE_ENDPOINT:
        return iface.connected_endpoint

    if iface.connected_endpoints:
        return iface.connected_endpoints[0]

    return None


def get_remote_interface_LAG(iface: Interface) -> Optional[Interface]:  # noqa: C901
    """Get the remote interface the given LAG Interface if connected to.

    Parameters
    ----------
    iface : Interface
        The Interface to trace from.

    Returns
    -------
    Interface or None
        Return a dcim.models.device_components.Interface object, or None.
    """
    device_name = iface.device.name
    lag_members = get_LAG_members(iface)
    if len(lag_members) == 0:
        return None

    peer_ifaces = []
    for iface in lag_members:
        peer_iface = None
        if SINGLE_CABLE_ENDPOINT:
            peer_iface = iface.connected_endpoint
        else:
            if iface.connected_endpoints:
                peer_iface = iface.connected_endpoints[0]

        if peer_iface is None or type(iface) != Interface:
            continue

        peer_ifaces.append(peer_iface)

    if len(peer_ifaces) == 0:
        return None

    lag = peer_ifaces[0].lag
    remote_device = peer_ifaces[0].device
    for peer_iface in peer_ifaces:
        if peer_iface.device != remote_device:
            raise NetBoxDataError(
                f"Members of LAG {iface} on device {device_name} are connected to different remote devices:"
                f"{remote_device} vs. {peer_iface.remote_device}"
            )

        if peer_iface.lag is not None and peer_iface.lag != lag:
            raise NetBoxDataError(
                f"At least one member of LAG {iface} on device {device_name} is part of a different LAG"
                f"on the remote end ({lag} vs. {iface.lag})"
            )

    if lag is None:
        raise NetBoxDataError(
            f"None of the members of LAG {iface} on device {device_name} connect an interface which are part of LAG"
        )

    return lag


def get_interface(device: Device, if_name: str) -> Optional[Interface]:
    """Look up Interface with name 'if_name' on the given 'device'.

    Returns 'None' if Interface doesn't exist.

    Parameters
    ----------
    device : Device
        The Device the interface exist on.
    if_name: str
        The name of the Interface.

    Returns
    -------
    Interface or None
        Return a dcim.models.device_components.Interface object, or None.
    """
    try:
        return Interface.objects.get(device=device, name=if_name)
    except Interface.DoesNotExist:
        return None


def interface_types_compatible(
    iface: Interface, type_to_connect: InterfaceTypeChoices
) -> bool:
    """Check if the given Interface is compatible with the given speed.

    Parameters
    ----------
    iface : Interface
        The Interface object to check compatibility against.
    type_to_connect: InterfaceTypeChoices
        An interface type to connect to the given iface.

    Returns
    -------
    bool
        True if the interfaces are compatible, False if not.
    """
    if iface.type == type_to_connect:
        return True

    if iface.type in INTERFACE_TYPE_COMPATIBILITY:
        return type_to_connect in INTERFACE_TYPE_COMPATIBILITY[iface.type]

    return False


def create_interface(
    device: Device,
    ifname: str,
    port_type: InterfaceTypeChoices,
    desc: str = "",
    script: Script = None,
) -> Interface:
    """Create a new interface.

    Parameters
    ----------
    device : Device
        The Device to create an Interface on.
    ifname: str
        Name of the Interface to create.
    port_type: InterfaceTypeChoices
        Type of the Interface to create.
    desc: str, optional
        Description to set in the interface.
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object.
    """
    iface = Interface(device=device, name=ifname, type=port_type, description=desc)

    iface.save()
    log_maybe(script, "success", f"Created interface {ifname} on device {device.name}")

    return iface


def get_or_create_interface(
    device: Device,
    ifname: str,
    port_type: InterfaceTypeChoices,
    desc: str = "",
    script: Script = None,
) -> tuple[Interface, bool]:
    """Look up Interface with name 'if_name' on the given 'device' or create if it isn't present.

    It will raise an NetBoxDataError if the Interfaces exists but has a different port_type.

    Parameters
    ----------
    device : Device
        The Device to create an Interface on.
    ifname: str
        Name of the Interface to create.
    port_type: InterfaceTypeChoices
        Type of the Interface to create.
    desc: str, optional
        Description to set in the interface.
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object.
    bool
        True if the Interface was created, False if it already existed.
    """
    res = Interface.objects.filter(device=device, name=ifname)

    if len(res) > 0:
        iface = res[0]
        if iface.type != port_type:
            raise NetBoxDataError(
                f"{get_port_string(iface)} exist, but has wrong type, expected {port_type} found {iface.type}"
            )

        log_maybe(script, "info", f"Found interface {ifname} on device {device.name}")
        return iface, False

    iface = create_interface(device, ifname, port_type, desc, script)

    return iface, True


def get_or_create_LAG_interface_with_members(
    device: Device,
    ifname: str,
    members: list[Interface],
    desc: Optional[str] = "",
    script: Optional[Script] = None,
) -> tuple[Interface, bool]:
    """Look up LAG Interface with name 'if_name' on the given 'device' or create it if it isn't present.

    If the LAG was created, set the given member interfaces to be part of this LAG, if it already existed
    validate that all given members are part of this LAG and raise an NetBoxDataError if they aren't.

    Parameters
    ----------
    device : Device
        The Device to create an Interface on.
    ifname: str
        Name of the Interface to create.
    members: list[Interface]
        A list of Interfaces in the LAG
    desc: str, optional
        Description to set in the interface.
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object.
    bool
        True if the Interface was created, False if it already existed.
    """
    lag, created = get_or_create_interface(
        device, ifname, InterfaceTypeChoices.TYPE_LAG, desc, script
    )

    for iface in members:
        # iface is not part of a LAG
        if iface.lag is None:
            iface.lag = lag
            iface.save()

        # iface already is part of a LAG
        if iface.lag != lag:
            raise NetBoxDataError(
                f"{get_port_string(iface)} should be placed in LAG {lag}, but is member of LAG {iface.lag}!"
            )

    return lag, created


def create_next_available_LAG_interface(
    device: Device,
    desc: Optional[str] = "",
    start_at: Optional[int] = None,
    override_basename: Optional[str] = None,
    script: Optional[Script] = None,
) -> Interface:
    """Create the next available LAG interface on the given device, using the given basename.

    Parameters
    ----------
    device : Device
        The Device to create an Interface on.
    desc: str, optional
        Description to set in the interface.
    start_at: int, optional
        Non-negative integer value denoting at which interface number to start.
        Usually derived from device's platform / manufacturer.
    override_basename: str, optional
        Override basename of LAG devices on this device, e.g. "ae", "bond", or "Port-Channel".
        Usually derived from device's platform / manufacturer.
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object.
    """
    if override_basename:
        lag_basename = override_basename
        start_at_default = 1
    else:
        # This will raise a NetBoxDataError if we can't find a config
        lag_basename, start_at_default = get_device_lag_base_cfg(device)

    existing_lags = Interface.objects.filter(
        device=device, type=InterfaceTypeChoices.TYPE_LAG
    )

    next_lag_number = start_at_default
    if start_at is not None:
        try:
            next_lag_number = int(start_at)
            if start_at < 0:
                raise InvalidInput(
                    f"Invalid value for 'start_at' paramter, needs to be > 0: {start_at}"
                )
        except (TypeError, ValueError):
            raise InvalidInput(
                f"Invalid value for 'start_at' paramter, not an integer: {start_at}"
            )

    lag_re = re.compile(rf"^{lag_basename}(\d+)$")
    lag_numbers = []
    for lag in existing_lags:
        match = lag_re.search(lag.name)
        if match is None:  # pragma: nocover
            log_maybe(
                script,
                "warning",
                f"Found LAG {lag.name}, which didn't match basename {lag_basename}",
            )
            continue

        lag_numbers.append(int(match.group(1)))

    # Make 100% sure we're traversing the LAG indexes in ascending order
    for lag_number in sorted(lag_numbers):
        if lag_number > next_lag_number:
            break

        if lag_number == next_lag_number:
            next_lag_number += 1

    next_lag_name = f"{lag_basename}{next_lag_number}"

    lag, _ = get_or_create_interface(
        device, next_lag_name, InterfaceTypeChoices.TYPE_LAG, desc, script
    )
    return lag


def get_child_interfaces(iface: Interface) -> list[Interface]:
    """Look up all Interfaces of 'device' which have 'iface: Interfaces their parent."""
    return list(Interface.objects.filter(parent=iface))


def get_LAG_members(lag: Interface) -> list[Interface]:
    """Look up all Interfaces which have 'lag' Interfaces as their parent."""
    return list(Interface.objects.filter(lag=lag))


def create_vlan_unit(iface: Interface, vlan_id: int) -> Interface:
    """Create a unit / sub-interface on the given interface with the given 'vlan_id'.

    Parameters
    ----------
    iface : Interface
        Interface to create a VLAN unit on.
    vlan_id: int
        Numerical VLAN ID.

    Returns
    -------
    Interface
        Return a dcim.models.device_components.Interface object.
    """
    unit_ifname = "%s.%d" % (iface.name, vlan_id)

    # Check if this unit already exists
    try:
        Interface.objects.get(
            device=iface.device,
            name=unit_ifname,
        )
        raise InvalidInput(
            f"VLAN ID {vlan_id} already configured on {get_port_string(iface)}"
        )
    except Interface.DoesNotExist:
        pass

    vlan_unit = Interface(
        device=iface.device,
        name=unit_ifname,
        type=InterfaceTypeChoices.TYPE_VIRTUAL,
        parent=iface,
    )
    vlan_unit.save()

    return vlan_unit


def tag_interfaces(interfaces: list[Interface], tag_name: str) -> None:
    """Ensure all given interfaces have the given tag associated with them.

    Parameters
    ----------
    interfaces : list[Interface]
        List of Interfaces to assure tag is on.
    tag_name: str
        Name of tag to apply to Interfaces.
    """
    try:
        tag_obj = Tag.objects.get(name=tag_name)
    except Tag.DoesNotExist:
        raise NetBoxDataError(f"Can't find tag {tag_name} - dying of shame.")

    for iface in interfaces:
        tags = iface.tags.all()
        if tag_name not in tags:
            iface.tags.add(tag_obj)


def assign_IP_address_to_interface(
    iface: Interface,
    ip_str: str,
    custom_fields: Optional[dict] = None,
    script: Optional[Script] = None,
) -> None:
    """Assign an IP address to an Interface.

    Parameters
    ----------
    iface : Interface
        Interface to assing IP on.
    ip_str: str
        String represenation of IP address.
    custom_fields: dict, optional
        Dictionary containing custom field values to apply to IP address.
    script: Script, optional
        Script object this function is called from, used for logigng.
    """
    ips = IPAddress.objects.filter(address=ip_str, interface=iface)
    if ips:
        log_maybe(
            script,
            "info",
            f"IP {ip_str} already assigned to {iface} on device {iface.device.name}",
        )
        return

    ip_obj = IPAddress(address=ip_str)
    ip_obj.save()
    iface.ip_addresses.add(ip_obj)
    iface.save()

    if custom_fields:
        ip_obj.custom_field_data.update(custom_fields)
        ip_obj.save()

    log_maybe(
        script,
        "success",
        f"Assigned IP {ip_obj} to interface {iface} on device {iface.device.name}",
    )


################################################################################
#                       IPAM related helper functions                          #
################################################################################


def get_prefixes(
    role_slug: str,
    address_family: Literal[4, 6],
    is_container: Optional[bool] = True,
    custom_fields: Optional[dict] = None,
    tag_name: Optional[str] = None,
    vrf_name: Optional[str] = None,
) -> list[Prefix]:
    """Get all prefixes fulfilling the given criteria (ANDed).

    Parameters
    ----------
    role_slug : str
        The slug of the prefix role to search for.
    address_family : Literal[4, 6]
        The address family of the prefix to search for.
    is_container : Optional[bool]
        If the prefix has to be have status container (default True)
    custom_fields : Optional[dict]
        Additional custom fields to set searching for prefixes.
    tag_name : Optional[str]
        The name of the tag to search for on the prefix (if any)
    vrf_name : str
        The vrf to search for.

    Returns
    -------
    list[Prefix]
        A list of ipam.models.Prefix objects.
    """
    pfx_role = get_prefix_role(role_slug)
    if pfx_role is None:
        raise InvalidInput(f"Prefix role (slug) {role_slug} does not exist!")

    query_args = {
        "role": pfx_role,
    }

    if is_container:
        query_args["status"]: PrefixStatusChoices.STATUS_CONTAINER
    if tag_name is not None:
        query_args["tags__name__in"] = [tag_name]
    if custom_fields is not None:
        query_args["custom_field_data"] = custom_fields
    if vrf_name is not None:
        vrf = get_vrf(vrf_name)
        if vrf is None:
            raise InvalidInput(f"VRF {vrf_name} does not exist!")
        query_args["vrf__name"] = vrf.name

    pfxs = []

    # Manually check for correct AF, seems we can't query for it
    for pfx in Prefix.objects.filter(**query_args):
        if pfx.family != address_family:
            continue

        pfxs.append(pfx)

    return pfxs


def get_or_create_prefix(
    prefix: Union[netaddr.ip.IPNetwork, str],
    desc: str,
    role: Optional[Role] = None,
    script: Optional[Script] = None,
) -> tuple[Prefix, bool]:
    """Make sure the given prefix exists and return it.

    If the prefix exist, the function checks if the description and role are identical
    and issue a warning if they arent (if a script is given).
    If the prefix does not exist, it will be created including the given description and role.

    The function will return the prefix and if it has been created.

    Parameters
    ----------
    prefix : Union[netaddr.ip.IPNetwork, str]
        The prefix to create/lookup, either as netaddr.ip.IPNetwork or string.
    desc : str
        The description to set on the prefix (if created)
    role: Role, optional
        The role to set on the prefix (if created)
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Prefix
        Return a ipam.models.Prefix object.
    bool
        True if the prefix was created, False if it existed.
    """
    pfx = netaddr.ip.IPNetwork(prefix)

    npfxs = Prefix.objects.filter(prefix=pfx)

    if len(npfxs) > 1:
        raise NetBoxDataError(f"Multiple Prefixes found for {prefix}")

    elif len(npfxs) == 1:
        existing_pfx = npfxs[0]

        if existing_pfx.description == desc and existing_pfx.role == role:
            log_maybe(script, "info", f"Found existing prefix {existing_pfx}")
        else:
            if existing_pfx.description != desc:
                log_maybe(
                    script,
                    "warning",
                    f"Found existing prefix {existing_pfx} with unexpected description: {existing_pfx.description}",
                )
            if existing_pfx.role != role:
                role_str = ""
                if existing_pfx.role is not None:
                    role_str = existing_pfx.role.name
                log_maybe(
                    script,
                    "warning",
                    f"Found existing prefix {existing_pfx} with unexpected role: {role_str}",
                )

        return existing_pfx, False

    kwargs = {
        "prefix": pfx,
        "description": desc,
    }
    if role is not None:
        kwargs["role"] = role

    pfx = Prefix(**kwargs)
    pfx.save()
    log_maybe(script, "success", f"Created prefix {pfx} with description {desc}")

    return pfx, True


def get_or_create_prefix_from_ip(
    ip_addr: Union[IPAddress, netaddr.ip.IPNetwork, str],
    desc: str,
    role: Optional[Role] = None,
    script: Optional[Script] = None,
) -> tuple[Prefix, bool]:
    """This wraps get_or_create_prefix() and derives the IP network of the given IP before calling get_or_create_prefix.

    Parameters
    ----------
    ip_addr : Union[IPAddress, netaddr.ip.IPNetwork, str]
        The IP to derive the prefix from.
    desc : str
        The description to set on the prefix (if created)
    role: Role, optional
        The role to set on the prefix (if created)
    script: Script, optional
        Script object this function is called from, used for logigng.

    Returns
    -------
    Prefix
        Return a ipam.models.Prefix object.
    bool
        True if the prefix was created, False if it existed.
    """
    if isinstance(ip_addr, IPAddress):
        ip_addr = str(ip_addr)
    ip = netaddr.ip.IPNetwork(ip_addr)
    pfx = f"{ip.network}/{ip.prefixlen}"

    return get_or_create_prefix(pfx, desc, role, script)


def get_prefix_role(slug: str) -> Optional[Role]:
    """Return the prefix Role object for the given role slug or None if it doesn't exist.

    Parameters
    ----------
    slug : str
        Slug of the prefix role to query.

    Returns
    -------
        Role or None
            Returns an ipam.models.Role object, or None.
    """
    try:
        return Role.objects.get(slug=slug)
    except Role.DoesNotExist:
        return None


def get_interface_IPs(iface: Interface) -> list[IPAddress]:
    """Retrieve all IPAddresses configured on the given interface.

    Parameters
    ----------
    iface : Interface
        Interface to query IPs of.

    Returns
    -------
        list[IPAddress]
            Returns a list of ipam.models.IPAddress objects.
    """
    return list(IPAddress.objects.filter(interface=iface))


def get_interface_IP(iface: Interface, ip: str) -> Optional[IPAddress]:
    """Check if the given IPAddress is configured on the given Interface.

    If it is return it, if it is multiple times raise an NetBoxDataError, if it isn't return None.

    Parameters
    ----------
    iface: Interface
        Interface to get IP of.
    ip: str
        IP to check for.

    Returns
    -------
    IPAddress or None
        Returns an ipam.models.IPAddress object, or None.
    """
    ips = IPAddress.objects.filter(address=ip, interface=iface)

    if not ips:
        return None

    if len(ips) > 1:
        raise NetBoxDataError(
            f"Found IP {ip} assigned to interface {iface} on {iface.device.name} assigned multiple times!"
        )

    return ips[0]


def get_next_free_IP_from_pools(
    pools: list[Prefix],
    script: Optional[Script] = None,
) -> Optional[IPAddress]:
    """Get the next free IPAddress from the given Prefix pool(s).

    Parameters
    ----------
    pools : list[Prefix]
        A list of ipam.models.Prefix objects, representing the pools(s) to carve from
    script : Script, optional
        The script object to use for logging (if desired)

    Returns
    -------
    IPAddress, optional
        An ipam.models.IPAddress object, or None
    """
    for pfx in pools:
        if not pfx.is_pool:
            log_maybe(
                script,
                "warning",
                "Should carve an IP from prefix {pfx}, which isn't a pool.",
            )

        ip_str = pfx.get_first_available_ip()
        if ip_str is None:
            log_maybe(script, "info", f"Pool {pfx} is depleted, moving on.")
            continue

        plen = 32 if pfx.family == AF_IPv4 else 128
        free_ip = IPAddress(address=f"{ip_str.split('/')[0]}/{plen}")
        free_ip.save()
        return free_ip

    log_maybe(
        script,
        "warning",
        "Looks like all pools are depleted *sniff*: "
        + ", ".join([str(p) for p in pools]),
    )
    return None


def get_next_free_prefix_from_prefixes(  # noqa: C901
    containers: list[Prefix],
    prefix_length: int,
    description: str,
    prefix_role_slug: Optional[str] = None,
    is_pool: Optional[bool] = False,
    custom_fields: Optional[dict] = None,
    vrf_name: Optional[str] = None,
) -> Prefix:
    """Get the next free prefix from the given Prefix container(s).

    If no Prefix role is found for the given prefix_role_slug this will raise an InvalidInput exception.

    If a prefix of prefix_length can't be carved from the given container(s), this will return None.

    Parameters
    ----------
    containers : list[Prefix]
        A list of ipam.models.Prefix objects, representing the container(s) to carve from
    prefix_length : int
        Prefix-length of the prefix to carve
    description : str
        The description for the new Prefix
    prefix_role_slug : Optional[str]
        Slug of the PrefixRole to assign to the new prefix (if any)
    is_pool : Optional[bool]
        Whether or not the new prefix shalt be a pool (default False)
    custom_fields : Optional[dict]
        Custom fields to set for the new prefix
    script : Script
        The script object to use for logging (if desired)
    vrf_name: str
        String representing the VRF name

    Returns
    -------
    Prefix
        An ipam.models.Prefix object, or None
    """
    # Prepare parameters for the Prefix to create
    new_prefix_args = {
        "description": description,
        "is_pool": is_pool,
    }

    if prefix_role_slug is not None:
        new_prefix_args["role"] = get_prefix_role(prefix_role_slug)
        if new_prefix_args["role"] is None:
            raise InvalidInput(f"Prefix role (slug) {prefix_role_slug} does not exist!")

    if custom_fields is not None:
        new_prefix_args["custom_field_data"] = custom_fields

    if vrf_name is not None:
        vrf = get_vrf(vrf_name)
        if vrf is None:
            raise InvalidInput(f"VRF {vrf_name} does not exist!")

        new_prefix_args["vrf"] = vrf

    for pfx in containers:
        # We do not want to assign the whole container
        if prefix_length == pfx.mask_length:
            continue

        # Get a list of all available sub-prefixes (type IPNetwork)
        avail_pfxs = pfx.get_available_prefixes().iter_cidrs()
        for apfx in avail_pfxs:
            if apfx.prefixlen > prefix_length:
                continue

            new_prefix = Prefix(
                prefix=IPNetwork("%s/%s" % (apfx.network, prefix_length)),
                **new_prefix_args,
            )
            new_prefix.save()

            return new_prefix

    return None


def get_next_free_prefix_from_container(
    container_role_slug: str,
    address_family: Literal[4, 6],
    prefix_length: int,
    description: str,
    container_tag_name: Optional[str] = None,
    container_custom_fields: Optional[str] = None,
    prefix_role_slug: Optional[str] = None,
    is_pool: Optional[bool] = False,
    script: Optional[Script] = None,
) -> Prefix:
    """Get the next free prefix from the available Prefix container(s) of the given role.

    This will look up prefix(es) with the given PrefixRole and optionally a tag
    and carve out the next available prefix of the given prefix-length from it.

    If no PrefixRole is found for the given container_role_slug or pfx_role string,
    the (optional) Tag doesn't exist, or no container prefixes are found, this will
    raise a InvalidInput exception.

    Parameters
    ----------
    container_role_slug : str
        Slug of the PrefixRole to use looking up the container prefix(es)
    address_family : Literal[4, 6]:
        The address family of the prefix to search for
    prefix_length : int
        Prefix-length of the prefix to carve
    description : str
        The description for the new Prefix
    container_tag_name : Optional[str]
        Name of the Tag to use to filter container prefixes (if any)
    container_custom_fields : Optional[dict]
        The custom fields to filter the container by (if any)
    prefix_role_slug : Optional[str]
        Slug of the PrefixRole to assign to the new prefix (if any)
    is_pool : Optional[bool]
        Whether or not the new prefix shalt be a pool (default False)
    script : Script
        The script object to use for logging (if desired)

    Returns
    -------
    Prefix
        An ipam.models.Prefix object.
    """
    containers = get_prefixes(
        container_role_slug,
        address_family=address_family,
        is_container=True,
        custom_fields=container_custom_fields,
        tag_name=container_tag_name,
    )
    if len(containers) == 0:
        err_msg = f"No container prefix found for role (slug) {container_role_slug}"
        if container_tag_name is not None:
            err_msg += f" and tag {container_tag_name}"
        if container_custom_fields is not None:
            err_msg += f" and custom fields {container_custom_fields}"
        raise InvalidInput(err_msg)

    msg = "Found container prefixes {}".format(", ".join(str(p) for p in containers))

    new_prefix = get_next_free_prefix_from_prefixes(
        containers,
        prefix_length,
        description,
        prefix_role_slug,
        is_pool,
    )
    if new_prefix is None:
        raise NetBoxDataError(f"{msg}, but no free prefix available *sniff*")

    log_maybe(script, "success", f"{msg}, created prefix {new_prefix}")
    return new_prefix


def get_IPs_from_IPSet(ipset: IPSet, prefix_length: int) -> list[IPNetwork]:
    """Get the IPs from an IPSet."""
    ips = []

    for ip_addr in ipset:
        ips.append(IPNetwork(f"{ip_addr}/{prefix_length}"))

    return ips


def get_vrf(vrf_name: str) -> Optional[VRF]:
    """Get the VRF with the given name.

    This will return None, if no VRF with the given name exists.

    Parameters
    ----------
    vrf_name : str
        The name of the colo to look up.

    Returns
    -------
    VRF
        A ipam.models.VRF object, or None
    """
    try:
        return VRF.objects.get(name=vrf_name)
    except VRF.DoesNotExist:
        return None


################################################################################
#                        Tag related helper functions                          #
################################################################################


def get_tag(name: str) -> Optional[Tag]:
    """Return the Tag with the given name, if it exists, or None if it doesn't.

    Parameters
    ----------
    name : str
        Name of the Tag to query for.

    Returns
    -------
    Tag or None
        Returns a extras.models import Tag object, or None.
    """
    try:
        return Tag.objects.get(name=name)
    except Tag.DoesNotExist:
        return None


def get_or_create_tag(
    name: str, color: Optional[ColorChoices] = None
) -> tuple[Tag, bool]:
    """Get a tag from the DB or create it if it's present.

    Check if a Tag with the given name exists in the DB an return it,
    or, if it doesn't exist, create a Tag with the given name and color.

    Parameters
    ----------
    name : str
        Name of the Tag to query for.
    color: ColorChoices, optional
        Color to set to Tag, if it's created.

    Returns
    -------
    Tag
        Returns a extras.models import Tag object
    bool
        True if the tag was created, False if it existed.
    """
    try:
        return Tag.objects.get(name=name), False
    except Tag.DoesNotExist:
        pass

    # Create tag with given color
    if color is not None:
        tag_obj = Tag(name=name, color=color)
        tag_obj.save()
        return tag_obj, True

    # Create tag with default values
    tag_obj = Tag(name=name)
    tag_obj.save()

    return tag_obj, True
