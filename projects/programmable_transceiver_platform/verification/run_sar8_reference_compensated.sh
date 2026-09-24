#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-reference-compensated adc/sar8_reference_compensated_screen.py rf_references reuse transceiver-adc-sar8-reference-reservoir
