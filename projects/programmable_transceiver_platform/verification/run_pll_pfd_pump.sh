#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pll-pfd-pump pll/pfd_pump_screen.py rf_references
