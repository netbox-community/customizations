#!/usr/bin/python3

"""Common constants for items in NetBox."""

CIRCUIT_TYPE_SLUG_DARK_FIBER = "dark-fiber"

DEVICE_ROLE_SLUG_CS = "console-server"
DEVICE_ROLE_SLUG_EDGE_ROUTER = "edge-router"

PLATFORM_SLUG_EOS = "eos"
PLATFORM_SLUG_JUNOS = "junos"
PLATFORM_SLUG_JUNOS_EVO = "junos-evo"

PREFIX_ROLE_SLUG_LOOPBACK_IPS = "loopback-ips"
PREFIX_ROLE_SLUG_SITE_LOCAL = "site-local"
PREFIX_ROLE_SLUG_TRANSFER_NETWORK = "transfer-network"

# Tags
TAG_NAME_NET_DHCP = "NET:DHCP"
TAG_NAME_NET_OOBM = "NET:OOBM"

# LAG basenames

PLATFORM_TO_LAG_BASENAME_MAP = {
    "eos": ("Port-Channel", 1),
    "junos": ("ae", 0),
    "junos-evo": ("ae", 0),
    "nxos": ("Port-Channel", 1),
}

MANUFACTURER_TO_LAG_BASENAME_MAP = {
    "arista": ("Port-Channel", 1),
    "cisco": ("Port-Channel", 1),
    "juniper": ("ae", 0),
}
