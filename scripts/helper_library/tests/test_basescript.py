#!/usr/bin/python3


from copy import deepcopy
from django.test import TestCase
import json

import scripts.common.utils as utils
from scripts.common.basescript import AbortScript, CommonAPIScript
from scripts.common.errors import InvalidInput, NetBoxDataError


def setUpModule() -> None:
    pass


class TestScriptBasic(CommonAPIScript):
    def run_method(self, data, commit):
        req_data = self.get_request_data(data)

        # successful returns
        if req_data.get("return string"):
            utils.log_maybe(self, "info", "Fourty")
            utils.log_maybe(self, "success", "Two")
            return "Fourtytwo"
        if req_data.get("return dict"):
            return {
                "magic key": 42,
            }

        # errors
        if req_data.get("InvalidInput"):
            raise InvalidInput("InvalidInput error")
        if req_data.get("NetBoxDataError"):
            raise NetBoxDataError("NetBoxDataError error")
        if req_data.get("Exception"):
            raise Exception("Oh noes!")


class TestScriptWithParamValidation(CommonAPIScript):
    def run_method(self, data, commit):
        req_data = self.get_request_data(data)

        self.validate_parameters(req_data, getattr(self, "validator_map", {}))


RET_DICT_TEMPLATE = {
    "success": False,
    "logs": [],
    "ret": None,
    "errmsg": None,
}


class ScriptTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Run once per TestCase instance."""
        pass

    # Test get_request_data(), logging, error handling, and returns
    def test_script_missing_request_param(self):
        script = TestScriptBasic()

        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite missing 'request' parameter!",
        ):
            script.run({}, False)

    def test_script_string_output(self):
        script = TestScriptBasic()

        req = '{"return string": true}'
        expected = {
            "success": True,
            "logs": [
                {"sev": "info", "msg": "Fourty"},
                {"sev": "success", "msg": "Two"},
            ],
            "ret": "Fourtytwo",
            "errmsg": None,
        }

        res = script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), res)

    def test_script_dict_output(self):
        script = TestScriptBasic()

        req = {"return dict": True}
        expected = deepcopy(RET_DICT_TEMPLATE)
        expected.update(
            {
                "success": True,
                "ret": {
                    "magic key": 42,
                },
            }
        )
        res = script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), res)

    def test_script_InvalidInput_error(self):
        script = TestScriptBasic()

        req = '{"InvalidInput": true}'
        expected = deepcopy(RET_DICT_TEMPLATE)
        expected.update(
            {
                "success": False,
                "errmsg": "InvalidInput error",
            }
        )
        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite InvalidInput!",
        ):
            script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), script.output)

    def test_script_NetBoxDataError_error(self):
        script = TestScriptBasic()

        req = '{"NetBoxDataError": true}'
        expected = deepcopy(RET_DICT_TEMPLATE)
        expected.update(
            {
                "success": False,
                "errmsg": "NetBoxDataError error",
            }
        )
        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite NetBoxDataError!",
        ):
            script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), script.output)

    def test_script_uncaught_Exception(self):
        script = TestScriptBasic()

        req = '{"Exception": true}'
        expected = deepcopy(RET_DICT_TEMPLATE)
        expected.update(
            {
                "success": False,
                "errmsg": "An unexpected error occured: Oh noes!",
            }
        )
        with self.assertRaises(
            Exception,
            msg=f"Script not aborted despite Exception!",
        ):
            script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), script.output)

    def test_script_invalid_JSON(self):
        script = TestScriptBasic()

        req = "{ JSON is quite picky, right?"
        expected = deepcopy(RET_DICT_TEMPLATE)
        expected.update(
            {
                "success": False,
                "errmsg": "Failed to unmarshal request JSON: Expecting property name enclosed in double quotes: line 1 column 3 (char 2)",
            }
        )
        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite invalid JSON input!",
        ):
            script.run({"request": req}, False)
        self.assertEqual(json.dumps(expected), script.output)

    # Test validate_parameters()

    def test_validate_parameters_invalid_JSON(self):
        script = TestScriptWithParamValidation()

        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite 'request' param being a string!",
        ):
            # Invalid params, should be dict, is string
            script.run({"request": "42"}, False)

    def test_validate_parameters_missing_param(self):
        script = TestScriptWithParamValidation()

        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite 'request' param being a string!",
        ):
            script.validator_map = {
                "non_existing_param": None,
            }
            script.run({"request": {}}, False)

    def test_validate_parameters_existence_check(self):
        script = TestScriptWithParamValidation()

        req = {
            "vid": 42,
        }
        script.validator_map = {
            "vid": None,
        }
        script.run({"request": req}, False)

    def test_validate_parameters_unknown_validator(self):
        script = TestScriptWithParamValidation()

        req = {
            "ip": "192.0.2.23",
            "pfx": "192.0.2.42/24",
            "vid": 42,
        }

        with self.assertRaises(
            AbortScript,
            msg=f"Script not aborted despite unknown validator referenced!",
        ):
            script.validator_map = {"vid": "non-existing-validator"}
            script.run({"request": req}, False)

    def test_validate_parameters_valid_validators(self):
        script = TestScriptWithParamValidation()

        req = {
            "ip": "192.0.2.23",
            "pfx": "192.0.2.42/24",
            "vid": 42,
        }

        script.validator_map = {
            "ip": "ip",
            "pfx": "prefix",
            "vid": "vlan_id",
            # skip testing device to not add requirement on DB fixtures
        }
        script.run({"request": req}, False)
