from extras.choices import JobResultStatusChoices
from extras.reports import Report
from dcim.models import Device
from collections import OrderedDict
import logging
import traceback
from django.utils import timezone



logger = logging.getLogger(__name__)


class SerialReport(Report):
    description = "Check if devices have a serial and no duplicate serial exists"

    def __init__(self):
        repeated = self._check_repeated()
        if len(repeated) > 0:
            for serial in repeated:
                setattr(self.__class__,
                    f'test_Serial_{serial}_repeated',
                    staticmethod(self._repeated_serial_wrapper(serial, repeated[serial] )))
        self.setup()

    def _repeated_serial_wrapper(self, serial, devices):
        
        def run_test():
            self._repeated_serial(serial, devices)
        
        return run_test

    def _repeated_serial(self, serial, devices):
        for device in devices:
            self.log_failure(device, f"Device with serial {serial} repeated")
            
    def _check_repeated(self):
        device_serials = {}
        for device in Device.objects.all():
            if device.serial != '':
                if device.serial not in device_serials:
                    device_serials[device.serial] = [device]
                else:
                    device_serials[device.serial].append(device)
        repeated_serials = {}
        for serial in device_serials:
            if len(device_serials[serial]) > 1:
                repeated_serials[serial] = device_serials[serial]
        return repeated_serials

    

    @property
    def name(self):
        return "Device Serial Validation"

    def test_Device_has_serial(self):
        for device in Device.objects.all():
            if device.serial != '':
                self.log_success(device, "Device have serial configured")
            else:
                self.log_failure(device, "Device hasn't serial configured")

    def setup(self):
        self._results = OrderedDict()
        self.active_test = None
        self.failed = False

        self.logger = logging.getLogger(f"netbox.reports.{self.full_name}")

        # Compile test methods and initialize results skeleton
        test_methods = {}
        for method in dir(self):
            if method.startswith('test_') and callable(getattr(self, method)):
                method_array = method.split("_")
                method_array = method_array[1:]
                name = " ".join(method_array)
                test_methods[name] = method
                self._results[name] = OrderedDict([
                    ('success', 0),
                    ('info', 0),
                    ('warning', 0),
                    ('failure', 0),
                    ('log', []),
                ])
        if not test_methods:
            raise Exception("A report must contain at least one test method.")
        self.test_methods = test_methods

    def run(self, job_result):
        """
        Run the report and save its results. Each test method will be executed in order.
        """
        self.logger.info(f"Running report")
        job_result.status = JobResultStatusChoices.STATUS_RUNNING
        job_result.save()

        try:

            for method_name in self.test_methods:
                self.active_test = method_name
                test_method = getattr(self, self.test_methods[method_name])
                test_method()

            if self.failed:
                self.logger.warning("Report failed")
                job_result.status = JobResultStatusChoices.STATUS_FAILED
            else:
                self.logger.info("Report completed successfully")
                job_result.status = JobResultStatusChoices.STATUS_COMPLETED

        except Exception as e:
            stacktrace = traceback.format_exc()
            self.log_failure(None, f"An exception occurred: {type(e).__name__}: {e} <pre>{stacktrace}</pre>")
            logger.error(f"Exception raised during report execution: {e}")
            job_result.set_status(JobResultStatusChoices.STATUS_ERRORED)

        job_result.data = self._results
        job_result.completed = timezone.now()
        job_result.save()

        # Perform any post-run tasks
        self.post_run()
