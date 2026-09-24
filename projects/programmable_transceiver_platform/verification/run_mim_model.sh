#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-mim-model adc/mim_model_screen.py rf_references reuse transceiver-adc-sar-acquisition
