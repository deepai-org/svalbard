#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-current-dc dac/current_steering8_dc.py rf_references reuse transceiver-adc-sar8-strong-mask-frames
