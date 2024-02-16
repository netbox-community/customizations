# MIT License
# 
# Copyright (c) 2023 Per von Zweigbergk
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from extras.scripts import *

from dcim.models import Device, Rack, RackReservation

class ChangeManager:
    """
    Convenience context manager that ensures that NetBox are snapshotted before any changes, and cleaned and saved
    after said changes. Any uncaught exceptions within the concept manager will inhibit saving of those changes.
    """
    def __init__(self, obj):
        self.obj = obj
    def __enter__(self):
        if self.obj.pk and hasattr(self.obj, 'snapshot'):
            self.obj.snapshot()
    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is not None:
            return False # re-raise any exceptions without saving changes
        self.obj.full_clean()
        self.obj.save()

def flip_rack(rack, log_f=lambda s:None):
    devices = Device.objects.filter(rack=rack, position__isnull=False)
    # Calculate new positions for all devices. We pre-calculated this here because we are about to remove all
    # devices from their existing positions, thus temporarilly removing the information about positions.
    new_positions = [rack.u_height - (device.position - 1) - (device.device_type.u_height - 1) for device in devices]

    # Remove all racked devices from rack temporarilly to avoid clashes
    for device in devices:
        with ChangeManager(device):
            log_f(f"Removing {device} from position {device.position}")
            device.position = None

    # Flip the units on the rack
    with ChangeManager(rack):
        rack.desc_units = not rack.desc_units
        log_f(f"Setting rack {rack} desc_units={rack.desc_units}")

    # Add the devices back to their new positions
    for device, position in zip(devices, new_positions):
        with ChangeManager(device):
            log_f(f"Adding {device} to position {position}")
            device.position = position

    # Deal with rack reservations
    for reservation in RackReservation.objects.filter(rack=rack):
        with ChangeManager(reservation):
            reservation.units = sorted(rack.u_height - (unit - 1) for unit in reservation.units)
            log_f(f"Updating reservation {reservation.pk} units to {repr(reservation.units)}")

class RackFlipper(Script):
    class Meta:
        name = "Rack flipper"
        description = "This scripts flips a rack between ascending and descending units while preserving their physical locations"
    
    rack = ObjectVar(
        description="The rack to update",
        model=Rack,
        required=True
    )

    def run(self, data, commit):
        flip_rack(data['rack'], self.log_info)
