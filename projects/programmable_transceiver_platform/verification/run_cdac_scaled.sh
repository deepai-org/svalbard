#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-cdac-scaled adc/cdac_scaled_screen.py rf_references
