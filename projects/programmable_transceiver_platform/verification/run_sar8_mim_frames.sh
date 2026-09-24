#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-mim-frames adc/sar8_mim_frames_screen.py rf_references reuse transceiver-adc-sar8-strong-mask-frames
