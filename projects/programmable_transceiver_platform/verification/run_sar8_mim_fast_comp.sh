#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-mim-fast-comp adc/sar8_mim_fast_comp_screen.py rf_references reuse transceiver-adc-sar8-mim-frames
