#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sample-driver-longmirror adc/sample_driver_longmirror_screen.py rf_references reuse transceiver-adc-sar-acquisition
