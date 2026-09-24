#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-driver-impedance reference/driver_impedance_screen.py rf_references reuse transceiver-adc-sar8-strong-mask-frames
