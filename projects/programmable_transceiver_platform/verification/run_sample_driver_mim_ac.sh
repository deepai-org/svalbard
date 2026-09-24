#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-driver-mim-ac adc/sample_driver_mim_ac_screen.py rf_references reuse transceiver-adc-sar8-strong-mask-frames
