#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-sine-speed quadrature/lo_sine_speed.py basic fresh
