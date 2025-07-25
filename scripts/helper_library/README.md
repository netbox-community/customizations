# NetBox custom scripts helper library

This library is intended to aid as a low-hanging entry point into NetBox scripting.

It abstracts away some of the "Django things" from the user and also provides insight/ideas into how to work with the Django models and how to build unit tests for NetBox scripts.

## Modules

### Common Exceptions

The [common/errors.py] library contain some two Exceptions used by this library.

The `InvalidInput` error is raised when something we got from output doesn't make sense or isn't found and a `NetBoxDataError` is raised when something inside our data looks fishy.

Both errors are handled by the `CommonScript*` wrappers and will be translated into an `AbortScript` error to abort the script with a nice error message.

### Base scripts

The [common/basescript.py] library contain some wrapper classes around the NetBox `Script` class.

`CommonScript` handles permission handling and acts according to the presence (or absence) of the following class-level variables:
 - require_user_and_group (bool): If True, validate user and group list, by default one is enough.
 - allowed_users (list): List of usernames allowed to execute this scripts
 - allowed_groups (list): List of groups (of users) allowed to execute this scripts
`CommonScript` should never be used directly.

All scripts inheriting from `CommonScript` are expected to implement

  run_method(data, commit)

which will be called when executed.

Both `CommonUIScript` and `CommonAPIScript` inherit from `CommonScript`, so they support above permission handling.

`CommonUIScript` does not add more fluff on top, "just" the permission handling.

The `CommonAPIScript` adds a parameter validation layer on top. API scripts are expected to have one `request` parameter which contains the JSON encoded input parameters for the script. The `get_request_data()` methods tried to retrieve these parameters from the given `data` dict and unmarshal the JSON data. If the `request` parameter is missing or unmarshalling the JSON data fails, it will raise an `InvalidInput` Exception.

The params dict is expected to be a (flat) dictionary holding the parameters of the script. Once it has been retrieved and unmarshalled validation should happen.
The

  validate_parameters(self, params: dict, key_to_validator_map: dict) -> None:

method provides low-hanging access to basic validation functions. The `key_to_validator_map` holds a map from the parameter key to a validation function as defined in the `VALIDATOR_MAP` within the [common/validators.py] module. A value of `None`` can be used to indicate that only the existence of a parameter should be checked if no fitting validator exists (yet). The validators module also provides additional validators to check more complex things (e.g. is "IP x within subnet Y?").

### Utils

The [common/utils.py] module provides a lot of wrapper functions to work with Devices, Interfaces, Front/Rear Ports (or any kind of `port`), Circuits and Terminations, Prefixes, IPs, Tags, etc.

I also provides helper functions to find Prefixes with certain constraints, carve the next available sub-prefix(es) from it, and get the IPs from these.

## Static analysis

This code is linted and formated according to `ruff` and `black`, both are configured in `pyproject.toml`.

The following Make targets exist to make your life easier:
 * `make lint` will run both checks and could (read: should) be used in a CI environment :)
 * `make format` will let `black` format the code as it sees fit
 * `make ruff-fix` will run `ruff --fix` and can aid with fixing some of its complains

## Testing scripts

Besides linting/formating enforcements, this repo contains unit tests for nearly all parts of this library.

For this `coverage` is run via `docker-compose`, as Django requires its own special testing environment which also requires a database instance.
Besides the NetBox container this also requires a PostgreSQL DB to be present, which will be set to NetBox baseline defaults by the Django test framework.
To simplify your unit-testing life, there is a `templates` fixture available in the `fixtures/` directory, see [fixtures/README.md] for details on what it contains, and [README.fixtures.md] on how to update it.

The end-to-end unit tests live in `tests/`.

To run them manually run `make coverage`.