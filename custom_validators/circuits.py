from django.db.models import Q

from extras.validators import CustomValidator


class CircuitInstallDateOnCreate(CustomValidator):
    """Require new circuits to have their install date filled out.
    Also prevent install dates from being removed from existing circuits.

    This helps your team migrate to requiring install dates if they previously
    were not. Using the simple validators to always require the date can
    break editing existing circuits with no install date where you don't
    actually know the original install date and don't want to fake it."""

    def validate(self, circuit):

        # Don't require install dates for circuits that haven't been active before
        if circuit.status in ("planned", "provisioning"):
            return

        # Check install date for new circuits
        if circuit.pk is None and not circuit.install_date:
            self.fail(
                f"Date Installed must contain a valid date.", field="install_date"
            )
        # Check install date for existing circuits
        # Relies on private field _prechange_snapshot
        elif not circuit.install_date:
            existing_date = circuit._prechange_snapshot.get("install_date")
            if existing_date:
                self.fail(
                    f"Date Installed must contain a valid date.", field="install_date"
                )


class CircuitCommitRateValidator(CustomValidator):
    """Ensure circuit commit rate doesn't exceed the termination speeds."""

    def validate(self, circuit):

        if (
            not circuit.pk
            or not circuit.commit_rate
            or not circuit.terminations.all().exists()
        ):
            return

        cr = circuit.commit_rate

        if circuit.terminations.filter(Q(port_speed__lt=cr) | Q(upstream_speed__lt=cr)):
            self.fail(
                f"Commit rate cannot be greater than the circuit termination port speeds",
                field="commit_rate",
            )


class CircuitTerminationValidator(CustomValidator):
    """Ensure circuit termination speeds aren't less than the circuit commit rate."""

    def validate(self, termination):

        cr = termination.circuit.commit_rate

        if not cr:
            return

        if termination.port_speed and termination.port_speed < cr:
            self.fail(
                "Termination port speed cannot be less than the "
                f"circuit commit rate ({cr:,} kbps).",
                field="port_speed",
            )
        elif termination.upstream_speed and termination.upstream_speed < cr:
            self.fail(
                "Termination upstream speed cannot be less than the "
                f"circuit commit rate ({cr:,} kbps).",
                field="upstream_speed",
            )
