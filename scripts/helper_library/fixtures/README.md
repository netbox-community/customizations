# Fixtures

This fixtures directory will be present as `/opt/fixtures/` within the NetBox container used for tests.

You can load any fixture(s) in your test by means of (e.g.)

    class ScriptTestCase(TestCase):
        fixtures = [
            "/opt/fixtures/topology.json",
        ]

## Getting fixtures from the DB

To remove the burden of re-creating the whole toplogy including DeviceType templates etc. for the tests,
we're using fixtures exported from a running Netbox instance.

To query fixtures from your NetBox instance (assuming you're using NetBox-docker), do the following:

    docker exec -ti netbox /bin/bash -l
    cd netbox/

    # Templates + base line
    ./manage.py dumpdata \
        circuits.circuittype \
        circuits.provider \
        dcim.region \
        dcim.site \
        dcim.manufacturer \
        dcim.devicetype \
        dcim.moduletype \
        dcim.modulebaytemplate \
        dcim.interfacetemplate \
        dcim.frontporttemplate \
        dcim.rearporttemplate \
        dcim.consoleporttemplate \
        dcim.consoleserverporttemplate \
        dcim.devicerole \
        dcim.platform \
        ipam.role \
    > templatedata.json

and transform this file into something readable / diffable via

    jq < templatedata.json > templates.json

Note that extras.customfield are not dumped, the one required custom field is created manually.

## templates.json

This includes (but is not limited to) the following models including some items commonly seen in networks and to provide a base line for running the unit tests:

### Organizational models

Sites
 * DC01
 * DC02
 * NET-META-ANY

### Circuit Models

Circuit Types
 * Dark Fiber

Circuit Providers
 * Provider1

### DCIM models

**Manufacturers**
 * Arista
 * Cisco
 * Common
  * Juniper
 * Mellanox

**Device Types** (including Interface, Front + Rear Port templates)
 * Common
  * 24-port LC/LC PP
 * Juniper
  * QFX10008
 * Mellanox
  * SN2010

**Module Types** (including Interface, Front + Rear Port templates)
 * Juniper
  * QFX10000-30C
  * QFX10000-36Q

**Platforms (slugs)**
 * eos
 * junos
 * junos-evo

**Device Roles (slugs)**
 * console-server
 * edge-router
 * patch-panel
 * peer
 * pe

### IPAM models

**Roles**
 * Loopback IPs
 * Transfer Network
 * Site Local