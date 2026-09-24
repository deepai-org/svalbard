#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dummy-driver-dc pll/dummy_driver_dc_screen.py
