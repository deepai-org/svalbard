#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sample-driver-op adc/sample_driver_op.py rf_references reuse transceiver-adc-sar-acquisition
