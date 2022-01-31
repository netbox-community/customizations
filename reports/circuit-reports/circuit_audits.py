import datetime

from circuits.choices import CircuitStatusChoices
from circuits.models import Circuit
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

        today = datetime.datetime.utcnow().date()
        one_month_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_1)
        three_months_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_3)

        for circuit_obj in deprovisioned_circuits:

            deprovision_date = circuit_obj.cf.get("deprovision_date")

            if not deprovision_date:
                self.log_failure(circuit_obj, "No deprovisioned date defined.")

            elif deprovision_date < three_months_ago:  # older than 3 months
                self.log_failure(
                    circuit_obj,
                    "Deprovisioned 3+ months ago ({}), time to decommission (non-billing)!".format(
                        deprovision_date
                    ),
                )

            elif deprovision_date < one_month_ago:  # older than 1 month
                self.log_warning(
                    circuit_obj,
                    "Deprovisioned 1 month ago ({})".format(deprovision_date),
                )

            else:
                self.log_success(circuit_obj)

    def test_check_decommissioned(self):

        decommed_circuits = Circuit.objects.filter(
            status=CircuitStatusChoices.STATUS_DECOMMISSIONED
        )

        today = datetime.datetime.utcnow().date()
        six_months_ago = today - datetime.timedelta(hours=MONTHS_IN_HOURS_6)
        three_weeks_left = six_months_ago + datetime.timedelta(hours=WEEKS_IN_HOURS_3)

        for circuit_obj in decommed_circuits:

            decomm_date = circuit_obj.cf.get("decomm_date")

            if not decomm_date:
                self.log_failure(circuit_obj, "No decommissioned date defined.")

            elif decomm_date < six_months_ago:  # older than 6 months
                self.log_warning(
                    circuit_obj,
                    "Circuit ready for deletion, Decommed on {}".format(decomm_date),
                )

            elif decomm_date < three_weeks_left:  # 3 weeks til 6 months old
                self.log_info(
                    circuit_obj,
                    "3 or less weeks until eligible for deletion, Decommed on {}".format(
                        decomm_date
                    ),
                )

            else:
                self.log_success(circuit_obj)
