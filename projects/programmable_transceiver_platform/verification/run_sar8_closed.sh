#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sar8-closed adc/sar8_closed_screen.py rf_references reuse transceiver-adc-cdac-scaled
