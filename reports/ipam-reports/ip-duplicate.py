from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Func, F

from ipam.choices import IPAddressRoleChoices
from ipam.models import IPAddress, Prefix
from extras.reports import Report


# UniqueIPReport was forked from https://gist.github.com/dgarros/acc23b4fd8d42844b8a41f695e6cb769
class UniqueIPReport(Report):
    description = "Validate that we don't have an IP address allocated multiple times in the network"

    def test_unique_ip(self):
        dcim_interface = ContentType.objects.get(app_label='dcim', model='interface')
        virtualization_vminterface = ContentType.objects.get(app_label='virtualization', model='vminterface')

        ip_duplicates = (IPAddress.objects
                         .exclude(role__in=(
                            IPAddressRoleChoices.ROLE_ANYCAST,
                            IPAddressRoleChoices.ROLE_VIP,
                            IPAddressRoleChoices.ROLE_VRRP
                         ))
                         .annotate(ip_host=Func(F("address"), function="HOST"))
                         .values_list(ArrayAgg('pk'), 'vrf')
                         .annotate(ip_host_count=Count('ip_host'))
                         .filter(ip_host_count__gt=1, assigned_object_id__isnull=False))
        for primary_keys, vrf, count in ip_duplicates:
            ip_objs = IPAddress.objects.filter(pk__in=primary_keys).prefetch_related('assigned_object')
            ips_formatted = []
            for ip in ip_objs[1:]:
                assignment = f'[{ip.assigned_object}]({ip.assigned_object.get_absolute_url()})'

                if ip.assigned_object_type in (dcim_interface, virtualization_vminterface):
                    device_or_vm = None
                    if ip.assigned_object_type == dcim_interface:
                        device_or_vm = ip.assigned_object.device
                    elif ip.assigned_object_type == virtualization_vminterface:
                        device_or_vm = ip.assigned_object.virtual_machine
                    if device_or_vm is not None:
                        assignment = f'[{device_or_vm}]({device_or_vm.get_absolute_url()}) / {assignment}'

                ips_formatted.append(f'[{ip}]({ip.get_absolute_url()}) ({assignment})')

            self.log_failure(ip_objs[0], f'has {count - 1} duplicate IP(s): {", ".join(ips_formatted)}')


class UniquePrefixReport(Report):
    description = "Validate that we don't have a Prefix allocated multiple times in a VRF"

    def test_unique_prefix(self):
        for prefix in Prefix.objects.all():
            duplicate_prefixes = Prefix.objects.filter(vrf=prefix.vrf, prefix=str(prefix.prefix)).exclude(pk=prefix.pk)
            if len(duplicate_prefixes) > 0:
                msg = f"has {len(duplicate_prefixes)} duplicate prefix(es)"
                self.log_failure(prefix, msg)
