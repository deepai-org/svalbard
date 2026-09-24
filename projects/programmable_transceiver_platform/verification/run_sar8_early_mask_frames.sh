#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-early-mask-frames adc/sar8_early_mask_frames_screen.py rf_references reuse transceiver-adc-sar8-driven
