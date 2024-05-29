from django.db.models import Count, Q

from dcim.models import Cable
from extras.scripts import Script, BooleanVar


class BrokenCableTerminations(Script):
    name = f'Find (partially) orphaned cables'
    description = f'Find cable terminations misising either the A or B termination'

    delete_orphans = BooleanVar(
        description="Delete orphaned cables (cable missing A and B terminations)"
    )

    delete_partials = BooleanVar(
        description="Delete partially orphaned cables (cable either missing A or B termination)"
    )

    def run(self, data, commit):
        cables = Cable.objects.annotate(
            aterm=Count('terminations', filter=Q(terminations__cable_end="A")),
            bterm=Count('terminations', filter=Q(terminations__cable_end="B")),
        ).filter(Q(bterm=0) | Q(aterm=0))
        self.log_info(f'Found {cables.count()} problematic cables in DB')
        for cable in cables:
            if cable.aterm == 0 and cable.bterm > 0:
                self.log_warning(
                    f'[{cable}](/dcim/cables/{cable.pk}/) is missing \'A\' side termination'
                    f'{" => deleting" if data["delete_partials"] else ""}')
                if data["delete_partials"]:
                    cable.delete()
            elif cable.aterm > 0 and cable.bterm == 0:
                self.log_warning(
                    f'[{cable}](/dcim/cables/{cable.pk}/) is missing \'B\' side termination'
                    f'{" => deleting" if data["delete_partials"] else ""}')
                if data["delete_partials"]:
                    cable.delete()
            else:
                self.log_warning(
                    f'[{cable}](/dcim/cables/{cable.pk}/) is orphaned'
                    f'{" => deleting" if data["delete_orphans"] else ""}')
                if data["delete_orphans"]:
                    cable.delete()
