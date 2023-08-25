from django.db.models import Q

from dcim.models import Cable
from extras.scripts import Script


class BrokenCableTerminations(Script):
    name = f'Find (partially) orphaned cables'
    description = f'Find cable terminations that are orphaned or missing either the A or B termination'

    def run(self, data, commit):
        cables = list(Cable.objects.filter(~Q(terminations__cable_end='A') & ~Q(terminations__cable_end='B')))
        for end in ['A', 'B']:
            if end == 'A':
                negate = 'A'
                include = 'B'
            else:
                negate = 'B'
                include = 'A'
            cable_side = Cable.objects.filter(~Q(terminations__cable_end=negate) & Q(terminations__cable_end=include))
            cables.extend(list(cable_side))
        self.log_info(f'Found {len(cables)} problematic cables')
        for cable in cables:
            if len(cable.a_terminations) == 0 and len(cable.b_terminations) > 0:
                self.log_warning(f'{cable.pk}: {cable} is missing \'A\' side termination')
            elif len(cable.a_terminations) > 0 and len(cable.b_terminations) == 0:
                self.log_warning(f'{cable.pk}: {cable} is missing \'B\' side termination')
            else:
                self.log_warning(f'{cable.pk}: {cable} is orphaned')
