# Make sure to install the dnspython module for this to work (pip3 install dnspython)

from dcim.choices import DeviceStatusChoices
from dcim.models import Device
from extras.reports import Report
import socket, dns.resolver

class Check_DNS_A_Record(Report):
    description = "Check if device's primary IPv4 has DNS records"

    def test_dna_a_record(self):
        for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
            if device.interfaces is None:
                continue
            if device.name is None:
                self.log_info(device, "No device name")
                continue
            if device.primary_ip4_id is not None:
                try:
                    addr = socket.gethostbyname(device.name)
                    ip4 = str(device.primary_ip4).split("/")[0]
                    if addr == ip4:
                        self.log_success(device)
                    else:
                        self.log_failure(device,"DNS: " + addr + " - Netbox: " + ip4)
                except socket.gaierror as err:
                    self.log_info(device, "No DNS Resolution")
            else:
                try:
                    addr = socket.gethostbyname(device.name)
                    self.log_warning(device, "No IPv4 set.  Could be: " + addr)
                except socket.gaierror as err:
                    self.log_info(device, "No IP or DNS found.")

class Check_DNS_AAAA_Record(Report):
    description = "Check if device's primary IPv6 has DNS records"

    def test_dns_aaaa_record(self):
        for device in Device.objects.filter(status=DeviceStatusChoices.STATUS_ACTIVE):
            if device.interfaces is None:
                continue
            if device.name is None:
                self.log_info(device, "No device name")
                continue
            if device.primary_ip6_id is not None:
                try:
                    aaaa = dns.resolver.query(device.name, "AAAA")
                    addr = str(aaaa[0])
                    ip6 = str(device.primary_ip6).split("/")[0]
                    if addr == ip6:
                        self.log_success(device)
                    else:
                        self.log_failure(device,"DNS: " + addr + " - Netbox: " + ip6)
                except dns.resolver.NoAnswer:
                    self.log_info(device, "No AAAA Record")
                except dns.resolver.NXDOMAIN:
                    self.log_info(device, "No such domain")
            else:
                try:
                    aaaa = dns.resolver.query(device.name, "AAAA")
                    addr = str(aaaa[0])
                    self.log_warning(device, "No IPv6 set.  Could be: " + addr)
                except dns.resolver.NoAnswer:
                    self.log_success(device)
                except dns.resolver.NXDOMAIN:
                    self.log_success(device)
