import datetime

from circuits.models import Circuit
from circuits.choices import CircuitStatusChoices
from extras.models import CustomFieldValue
from extras.reports import Report


WEEKS_IN_HOURS_3 = 24 * 21
MONTHS_IN_HOURS_1 = 24 * 30
MONTHS_IN_HOURS_3 = 24 * 90
MONTHS_IN_HOURS_6 = 24 * 180


class StatusDates(Report):
    """
    These reports rely on a couple custom fields existing:
        - Deprovision Date
        - Decomm Date
    """

    description = "Check status dates of circuits for discrepancies."

    def test_check_deprovisioned(self):

        deprovisioned_circuits = Circuit.objects.filter(
            status=CircuitStatusChoices.STATUS_DEPROVISIONING
        )

        deprovision_dates = CustomFieldValue.objects.filter(
            field__name="deprovision_date", obj_id__in=deprovisioned_circuits
        )

        # Get list of PKs for deprovisioned circuits to compare with
        # the custom field data later
        deprovisioned_pks = deprovisioned_circuits.values_list("pk", flat=True)

        today = datetime.datetime.utcnow().date()
        one_month_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_1)
        three_months_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_3)

        circuits_w_dates = []
        for circuit in deprovision_dates:

            circuit_obj = circuit.obj
            circuits_w_dates.append(circuit_obj.id)

            if not circuit.value:
                self.log_failure(circuit_obj, "No deprovisioned date defined.")

            elif circuit.value < three_months_ago:  # older than 3 months
                self.log_failure(
                    circuit_obj,
                    "Deprovisioned 3+ months ago ({}), time to decommission (non-billing)!".format(
                        circuit.value
                    ),
                )

            elif circuit.value < one_month_ago:  # older than 1 month
                self.log_warning(
                    circuit_obj, "Deprovisioned 1 month ago ({})".format(circuit.value)
                )

            else:
                self.log_success(circuit_obj)

        for missing in set(deprovisioned_pks) - set(circuits_w_dates):
            circuit_obj = Circuit.objects.get(pk=missing)
            self.log_failure(circuit_obj, "No deprovisioned date defined.")

    def test_check_decommissioned(self):

        decommed_circuits = Circuit.objects.filter(status=CircuitStatusChoices.STATUS_DECOMMISSIONED)

        decomm_dates = CustomFieldValue.objects.filter(
            field__name="decomm_date", obj_id__in=decommed_circuits
        )

        # Get list of PKs for decommed circuits to compare with
        # the custom field data later
        decommed_pks = decommed_circuits.values_list("pk", flat=True)

        today = datetime.datetime.utcnow().date()
        six_months_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_6)
        three_weeks_left = six_months_ago + datetime.timedelta(hours=WEEKS_IN_HOURS_3)

        circuits_w_dates = []
        for circuit in decomm_dates:

            circuit_obj = circuit.obj
            circuits_w_dates.append(circuit_obj.id)

            if not circuit.value:
                self.log_failure(circuit_obj, "No decommissioned date defined.")

            elif circuit.value < six_months_ago:  # older than 6 months
                self.log_warning(
                    circuit_obj,
                    "Circuit ready for deletion, Decommed on {}".format(circuit.value),
                )

            elif circuit.value < three_weeks_left:  # 3 weeks til 6 months old
                self.log_info(
                    circuit_obj,
                    "3 or less weeks until eligible for deletion, Decommed on {}".format(
                        circuit.value
                    ),
                )

            else:
                self.log_success(circuit_obj)

        for missing in set(decommed_pks) - set(circuits_w_dates):
            circuit_obj = Circuit.objects.get(pk=missing)
            self.log_failure(circuit_obj, "No decommissioned date defined.")
