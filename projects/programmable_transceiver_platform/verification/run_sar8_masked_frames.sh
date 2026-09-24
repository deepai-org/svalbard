#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-masked-frames adc/sar8_masked_frames_screen.py rf_references reuse transceiver-adc-sar8-driven
