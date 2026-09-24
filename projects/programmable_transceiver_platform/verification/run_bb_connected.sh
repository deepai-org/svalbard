#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-connected baseband/connected_screen.py baseline_wifi reuse transceiver-quadrature-lna-final
