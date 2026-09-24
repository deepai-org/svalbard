#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pll-charge-pump pll/charge_pump_screen.py rf_references
