#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-driver-mim-step adc/sample_driver_mim_step_screen.py rf_references reuse transceiver-adc-driver-mim-ac
