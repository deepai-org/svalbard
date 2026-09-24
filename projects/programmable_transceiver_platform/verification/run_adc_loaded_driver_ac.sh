#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-loaded-driver-ac adc/loaded_driver_ac.py wifi reuse transceiver-adc-loaded-driver
