#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pll-pfd-frequency pll/pfd_frequency_screen.py rf_references
