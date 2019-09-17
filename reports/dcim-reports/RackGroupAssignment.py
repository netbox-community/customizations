from dcim.models import Rack, RackGroup
from extras.reports import Report

class RackGroupAssignmentReport(Report):
    description = "Verify each rack is assigned to a Rack Group"
    def test_rack_group_assignment(self):
        for rack in Rack.objects.all():
            if rack.group_id is not None:
                self.log_success(rack.name)
            else:
                self.log_failure(rack.name, "No Rack Group assigned")
