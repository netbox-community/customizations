"""
Add multiple connections from one device to another
"""

from dcim.choices import LinkStatusChoices, CableTypeChoices, CableLengthUnitChoices
from dcim.models import Device, Cable
from django.db import transaction
from extras.models import Tag
from extras.scripts import Script, ChoiceVar, ObjectVar, StringVar, IntegerVar, MultiObjectVar
import re
from netbox.settings import VERSION
from tenancy.models import Tenant
try:
    from netbox.choices import ColorChoices
except ModuleNotFoundError:
    from utilities.choices import ColorChoices
from utilities.forms.constants import ALPHANUMERIC_EXPANSION_PATTERN
from utilities.forms.utils import expand_alphanumeric_pattern

NB_VERSION = [int(n) for n in VERSION.split('-')[0].split('.')]

NO_CHOICE = ()
# https://github.com/netbox-community/netbox/issues/8228
# Only apply to Netbox < v3.1.5
if NB_VERSION < [3, 1, 5]:
    NO_CHOICE = (
        ('', '---------'),
    )

TERM_CHOICES = (
    ('interfaces', 'Interfaces'),
    ('frontports', 'Front Ports'),
    ('rearports', 'Rear Ports'),
)

def expand_pattern(value):
    if not value:
        return ['']
    if re.search(ALPHANUMERIC_EXPANSION_PATTERN, value):
        return list(expand_alphanumeric_pattern(value))
    return [value]

class MultiConnect(Script):
    class Meta:
        name = "Multi Connect"
        description = "Add multiple connections from one device to another"

    device_a = ObjectVar(model=Device, label="Device A")
    termination_type_a = ChoiceVar(choices=TERM_CHOICES, label="Device A port type")
    termination_name_a = StringVar(label="Device A port name pattern", description="Example: ge-0/0/[5,7,12-23]")

    device_b = ObjectVar(model=Device, label="Device B")
    termination_type_b = ChoiceVar(choices=TERM_CHOICES, label="Device B port type")
    termination_name_b = StringVar(label="Device B port name pattern", description="Example: ge-0/0/[5,7,12-23]")

    cable_status = ChoiceVar(choices=LinkStatusChoices, default=LinkStatusChoices.STATUS_CONNECTED, label="Cable Status")
    cable_type = ChoiceVar(choices=NO_CHOICE+tuple(CableTypeChoices), required=False, label="Cable Type")
    cable_tenant = ObjectVar(model=Tenant, required=False, label="Cable Tenant")
    cable_label = StringVar(label="Cable Label pattern", required=False)
    cable_color = ChoiceVar(choices=NO_CHOICE+tuple(ColorChoices), required=False, label="Cable Color")
    cable_length = IntegerVar(required=False, label="Cable Length") # unfortunately there is no DecimalVar
    cable_length_unit = ChoiceVar(choices=NO_CHOICE+tuple(CableLengthUnitChoices), required=False, label="Cable Length Unit")
    cable_tags = MultiObjectVar(model=Tag, required=False, label="Cable Tags")

    def run(self, data, commit):
        device_a = data["device_a"]
        device_b = data["device_b"]
        ports_a = getattr(device_a, data["termination_type_a"]).all()
        ports_b = getattr(device_b, data["termination_type_b"]).all()

        terms_a = expand_pattern(data["termination_name_a"])
        terms_b = expand_pattern(data["termination_name_b"])
        if len(terms_a) != len(terms_b):
            return self.log_failure(f'Mismatched number of ports: {len(terms_a)} (A) versus {len(terms_b)} (B)')
        labels = expand_pattern(data["cable_label"])
        if len(labels) == 1:
            labels = [labels[0] for i in range(len(terms_a))]
        elif len(labels) != len(terms_a):
            return self.log_failure(f'Mismatched number of labels: {len(labels)} labels versus {len(terms_a)} ports')

        for i in range(len(terms_a)):
            term_a = [x for x in ports_a if x.name == terms_a[i]]
            if len(term_a) != 1:
                self.log_failure(f'Unable to find "{terms_a[i]}" in {data["termination_type_a"]} on device A ({device_a.name})')
                continue
            term_b = [x for x in ports_b if x.name == terms_b[i]]
            if len(term_b) != 1:
                self.log_failure(f'Unable to find "{terms_b[i]}" in {data["termination_type_b"]} on device B ({device_b.name})')
                continue
            cable_args = dict(
                type=data["cable_type"],
                status=data["cable_status"],
                tenant=data["cable_tenant"],
                label=labels[i],
                color=data["cable_color"],
                length=data["cable_length"],
                length_unit=data["cable_length_unit"],
            )
            if NB_VERSION < [3, 3, 0]:
                cable_args.update(dict(
                    termination_a=term_a[0],
                    termination_b=term_b[0],
                ))
            else:
                cable_args.update(dict(
                    a_terminations=term_a,
                    b_terminations=term_b,
                ))
            cable = Cable(**cable_args)
            try:
                with transaction.atomic():
                    cable.full_clean()
                    cable.save()
                    cable.tags.set(data["cable_tags"])
            except Exception as e:
                self.log_failure(f'Unable to connect {device_a.name}:{terms_a[i]} to {device_b.name}:{terms_b[i]}: {e}')
                continue
            self.log_success(f'Created cable from {device_a.name}:{terms_a[i]} to {device_b.name}:{terms_b[i]}')
