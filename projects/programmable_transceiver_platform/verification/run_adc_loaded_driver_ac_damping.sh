#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-loaded-driver-ac-damping adc/loaded_driver_ac.py damping reuse transceiver-adc-loaded-driver
