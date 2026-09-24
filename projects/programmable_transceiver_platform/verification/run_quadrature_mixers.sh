#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-quadrature-mixers quadrature/mixer_screen.py baseline_wifi reuse transceiver-quadrature-ring
