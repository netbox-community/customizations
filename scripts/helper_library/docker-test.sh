#!/usr/bin/env bash
set -euo pipefail

/opt/netbox/netbox/manage.py migrate

cd /tmp

# Run the test suite and generate a coverage report
#
# Note: You can add --keepdb here so the DB isn't thrown away and created on each run.
# This isn't part of the default call as this may to lead false results in some cases,
# however it yield as massive speed-up when activated, which is save for most tests.
coverage run --source='/opt/netbox/netbox/scripts/' --omit='/opt/netbox/netbox/scripts/tests/*' /opt/netbox/netbox/manage.py test --noinput /opt/netbox/netbox/scripts/tests/
coverage html -d /tmp/.cover
