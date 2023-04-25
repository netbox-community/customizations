"""
Identify and fix any IPAddress objects which have assigned_object_type_id but not assigned_object_id
or vice versa (fix by setting both to null)
"""

from extras.scripts import Script
from ipam.models import IPAddress

class FixAssignedIPs(Script):
    class Meta:
        name = "Fix Assigned IPs"
        description = "Fix any IP addresses which have assigned_object_type_id but not assigned_object_id, or vice versa"

    def run(self, data, commit):
        for ip in IPAddress.objects.filter(assigned_object_type_id__isnull=False, assigned_object_id__isnull=True):
            self.fix(ip)
        for ip in IPAddress.objects.filter(assigned_object_type_id__isnull=True, assigned_object_id__isnull=False):
            self.fix(ip)

    def fix(self, ip):
        old_assigned_object_type_id = ip.assigned_object_type_id
        old_assigned_object_id = ip.assigned_object_id
        ip.snapshot()
        ip.assigned_object_type_id = None
        ip.assigned_object_id = None
        ip.full_clean()
        ip.save()
        self.log_success(f"Fixed {ip} - had assigned_object_type_id={old_assigned_object_type_id}, assigned_object_id={old_assigned_object_id}")
