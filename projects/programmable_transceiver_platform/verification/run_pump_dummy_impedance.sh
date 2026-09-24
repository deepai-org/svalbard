#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-dummy-impedance pll/pump_dummy_impedance_screen.py basic reuse transceiver-pump-steering
