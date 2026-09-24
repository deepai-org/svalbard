#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-reservoir-model reference/reservoir_model_screen.py rf_references reuse transceiver-adc-sar8-strong-mask-frames
