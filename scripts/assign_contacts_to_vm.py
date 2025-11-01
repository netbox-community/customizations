"""
This script assigns primary & secondary contacts to a
virtual machine using a predetermined contact role
"""

from core.models import ObjectType
from extras.scripts import Script, ObjectVar
from tenancy.choices import ContactPriorityChoices
from tenancy.models import Contact, ContactAssignment, ContactRole
from virtualization.models import VirtualMachine

class AssignContactVM(Script):
    class Meta:
        name = "Assign Contacts to VM"
        description = "Takes a primary & secondary owner and assigns them to an existing VM"
        scheduling_enabled = False

    # Main form
    primary_contact = ObjectVar(label="Primary Owner", model=Contact)
    secondary_contact = ObjectVar(label="Secondary Owner", model=Contact)
    contact_role = ObjectVar(label="Contact Role", model=ContactRole)
    vm = ObjectVar(label="Virtual Machine", model=VirtualMachine)

    def run(self, data, commit):

        # Get VM object type
        vm_object_type = ObjectType.objects.get(model='virtualmachine')

        # Create contact assignments
        ownerPrimary = ContactAssignment(
            object_type=vm_object_type,
            object_id=data["vm"].id,
            contact=data["primary_contact"],
            role=contact_role,
            priority=ContactPriorityChoices.PRIORITY_PRIMARY,
        )
        ownerPrimary.full_clean()
        ownerPrimary.save()

        ownerSecondary = ContactAssignment(
            object_type=vm_object_type,
            object_id=data["vm"].id,
            contact=data["secondary_contact"],
            role=contact_role,
            priority=ContactPriorityChoices.PRIORITY_SECONDARY,
        )
        ownerSecondary.full_clean()
        ownerSecondary.save()

        self.log_success(f"Successfully assigned contacts {ownerPrimary.contact.name} & {ownerSecondary.contact.name} to {data['vm'].name}.")
