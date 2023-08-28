from django.db.models import Q

from dcim.models import Cable
from extras.scripts import Script


class BrokenCableTerminations(Script):
    name = f'Find (partially) orphaned cables'
    description = f'Find cable terminations misising either the A or B termination'

    def run(self, data, commit):
        cables = Cable.objects.annotate(
            aterm=Count('terminations', filter=Q(terminations__cable_end="A")),
            bterm=Count('terminations', filter=Q(terminations__cable_end="B")),
        ).filter(Q(aterm__gte=1, bterm=0) | Q(aterm=0, bterm__gte=1) | Q(aterm=0, bterm=0))
        self.log_info(f'Found {cables.count()} problematic cables in DB')
        for cable in cables:
            if cable.aterm == 0 and cable.bterm > 0:
                self.log_warning(f'{cable.pk}: {cable} is missing \'A\' side termination')
            elif cable.aterm > 0 and cable.bterm == 0:
                self.log_warning(f'{cable.pk}: {cable} is missing \'B\' side termination')
            else:
                self.log_warning(f'{cable.pk}: {cable} is orphaned')
