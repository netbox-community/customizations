#!/usr/bin/python3

"""Common NetBox Script wrapper classes.

This library provides the CommonUIScript and CommonAPIScript wrapper classes.

They provide ready to use validations for permissions (if required), as well as for
validating input parameters.  See the validators module for details on these.
"""

import json

from extras.scripts import Script

# Compatibility glue for NetBox version < 3.4.4
try:
    from utilities.exceptions import AbortScript
except ImportError:

    class AbortScript(Exception):
        """Raised to cleanly abort a script."""

        pass


import scripts.common.validators
from django.contrib.auth.models import User
from scripts.common.utils import InvalidInput, NetBoxDataError

################################################################################
#                      Base classes for NetBox Scripts                         #
################################################################################


class CommonScript(Script):  # pragma: no cover
    """Common wrapper class for NetBox scripts.

    No script should directly inherit from this class, but rather from
    - CommonUIScript for interactive scripts, or
    - CommonAPIScript for scripts to be called via the API

    This class handles permission handling and acts according to the presence (or absence)
    of the following class-level variables:
    - require_user_and_group (bool): If True, validate user and group list, by default one is enough.
    - allowed_users (list): List of usernames allowed to execute this scripts
    - allowed_groups (list): List of groups (of users) allowed to execute this scripts
    """

    def _get_require_user_and_group(self) -> bool:
        if not hasattr(self, "require_user_and_group"):
            return False

        require_user_and_group = getattr(self, "require_user_and_group")
        if not isinstance(require_user_and_group, bool):
            raise AbortScript(
                "Script class attribute 'require_user_and_group' must be boolean!"
            )
        if require_user_and_group:
            for attr in ["allowed_users", "allowed_groups"]:
                if not hasattr(self, attr):
                    raise AbortScript(
                        f"Script has 'require_user_and_group' set to True, but is missing {attr}"
                    )

        return require_user_and_group

    def validate_permissions(self) -> None:
        """Validate permissions of user/group running this script (if set)."""
        # request is None in unit tests
        if self.request is None:
            return

        username = self.request.user.username

        # Just bail if no checks are configured
        if not hasattr(self, "allowed_users") and not hasattr(self, "allowed_groups"):
            self.log_info("Everyone is allowed to execute this script.")
            return

        # By default we require user OR group check to succeed, shall we check both?
        require_user_and_group = self._get_require_user_and_group()

        if hasattr(self, "allowed_users"):
            users = getattr(self, "allowed_users")
            if not isinstance(users, list):
                raise AbortScript(
                    "Script class attribute 'allowed_users' must be a list!"
                )

            if username not in users:
                msg = f"User '{self.request.user.username}' is not allowed to execute this script!  "
                self.log_failure(msg)
                raise AbortScript(msg)

            if not require_user_and_group:
                return

        # Either there was no allowed_users attribute and it was satisfied or it's not required,
        # so check group permissions, if configured.
        if hasattr(self, "allowed_groups"):
            allowed_groups = getattr(self, "allowed_groups")
            if not isinstance(allowed_groups, list):
                raise Exception(
                    "Script class attribute 'allowed_groups' must be a list!"
                )

            user = User.objects.get(username=username)

            user_groups = [str(g) for g in user.groups.all()]
            if len(set(allowed_groups) & set(user_groups)) == 0:
                msg = f"User '{self.request.user.username}' is not allowed to execute this script (by group check)."
                self.log_failure(msg)
                raise AbortScript(msg)

        # If we're still here and didn't bail out, the user is allowed.
        self.log_info(
            f"User '{self.request.user.username}' is allowed to execute this script."
        )

    def run(self, data: dict, commit: bool = False) -> any:
        """Run method called by NetBox.

        This method needs to be implemented by script inheriting from this class.
        """
        raise NotImplementedError(
            "This class should never be used directly, inherit from CommonUIScript instead!"
        )


class CommonUIScript(CommonScript):  # pragma: no cover
    """This class acts as a base class for all user facing custom scripts used via the NetBox WebUI.

    Important note: Scripts that inherit fromt his class need to:
        - Implement the run_method() method
    """

    def run(self, data: dict, commit: bool = False) -> any:
        """Run method called by NetBox."""
        self.validate_permissions()

        try:
            return self.run_method(data, commit)
        except InvalidInput as e:
            raise AbortScript(f"Invalid input: {str(e)}")
        except NetBoxDataError as e:
            raise AbortScript(f"Potential data inconsistency error: {str(e)}")


class CommonAPIScript(CommonScript):
    """This class acts as a base class for custom scripts which should be solely run via API calls.

    Important note: Scripts that inherit fromt his class need to:
        - Implement the run_method() method

    Any Script which inherits from this class will always return a dictionary of the following format
    regard less of the fate of the script and how spectacularly it blew up or ran sucessfully:
        {
            "success": bool,
            "logs": list[dict],
            "ret": Optional[any],
            "errmsg": Optional[str],
        }

    Example for a successful run w/o return value
        {
            "success": True,
            "logs": [
                {"sev": "info", "msg": "Everyone is allowed to execute this script."},
                {"sev": "info", "msg": "IP 192.0.2.2/29 already configured on interface et18 on cr01.pad01"},
                {"sev": "info", "msg": "Gateway IP 192.0.2.1 already set."}
            ],
            "ret": null,
            "errmsg": null
        }

    Example for a successful run w/ return value (single value here, could be a dict, too)
        {
            "success": True,
            "logs": [
                {"sev": "info", "msg": "Everyone is allowed to execute this script."},
                {"sev": "info", "msg": "Found Device edge01.pad01"},
                {"sev": "success", "msg": "Device cr01.pad01 has capacity left for 62 (of 62)
                                           additional connections."},
                ...
            ],
            "ret": "192.0.2.42",
            "errmsg": null
        }

    Example of a failure:
        {
            "success": False,
            "logs": [
                {"sev": "info", "msg": "Everyone is allowed to execute this script."}
            ],
            "ret": null,
            "errmsg": "Given value "192.0.2.267/292" for parameter "ip" is not a valid IP prefix!"
        }
    """

    def _get_logs(self) -> list[str]:
        logs = []

        for entry in self.log:
            logs.append(
                {
                    "sev": entry[0],
                    "msg": entry[1],
                }
            )

        return logs

    def _ret_dict_json(self, success: bool, ret: any = None, errmsg: str = None) -> str:
        return json.dumps(
            {
                "success": success,
                "logs": self._get_logs(),
                "ret": ret,
                "errmsg": errmsg,
            }
        )

    def _ret_error(self, errmsg: str) -> dict:
        return self._ret_dict_json(False, errmsg=errmsg)

    def _ret_success(self, ret: any) -> dict:
        return self._ret_dict_json(True, ret)

    def get_request_data(self, data: dict) -> dict:
        """Retrieve script's request parameters and parse JSON.

        API scripts are expected to have one 'request' parameter which contains
        the JSON encoded input parameters for the script. This methods tried to
        retrieve these parameters from the given 'data' dict and unmarshal the JSON data.
        If the 'request' parameter is missing or unmarshalling the JSON data fails,
        it will raise an InvalidInput Exception.
        """
        try:
            req_data = data["request"]
            if isinstance(req_data, dict):
                return req_data

            return json.loads(req_data)
        except KeyError:
            raise InvalidInput("Missing 'request' parameter!")
        except (TypeError, json.JSONDecodeError) as e:
            raise InvalidInput("Failed to unmarshal request JSON: %s" % e)

    def validate_parameters(self, params: dict, key_to_validator_map: dict) -> None:
        """Validate parameters passed to the script.

        The params dict is expected to be a (flat) dictionary holding the parameters of the script,
        likely the output of get_request_data().

        The key_to_validator_map holds a map from the parameter key to a validation function as defined
        in the VALIDATOR_MAP within the common/validators module.  A value of None can be used to indicate
        that only the existence of a parameter should be checked if no fitting validator exists yet.
        """
        if not isinstance(params, dict):
            raise InvalidInput(
                f"Given 'params' is not a dictonary, but rather {type(params)}."
            )

        for key in sorted(key_to_validator_map.keys()):
            if key not in params:
                raise InvalidInput(f"Expected parameter '{key}' missing!")
            value = params[key]

            # Validator may be None, so we only validate parameter's existance
            validator = key_to_validator_map[key]
            if validator is None:
                continue

            validator_func = scripts.common.validators.VALIDATOR_MAP.get(validator)
            if validator_func is None:
                raise InvalidInput(f"No validator function found for {validator}!")

            validator_func(key, value)

    def run(self, data: dict, commit: bool = False) -> any:
        """Run method called by NetBox."""
        self.validate_permissions()

        try:
            return self._ret_success(self.run_method(data, commit))
        except InvalidInput as e:
            errmsg = str(e)
            self.output = self._ret_error(errmsg)
            raise AbortScript(f"Invalid input: {errmsg}")
        except NetBoxDataError as e:
            errmsg = str(e)
            self.output = self._ret_error(errmsg)
            raise AbortScript(f"Potential data inconsistency error: {errmsg}")
        except Exception as e:
            errmsg = str(e)
            self.output = self._ret_error(f"An unexpected error occured: {errmsg}")
            # Raise the Exception as-is to show the stack trace
            raise e
