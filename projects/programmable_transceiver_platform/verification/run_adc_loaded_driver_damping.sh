#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-loaded-driver-damping adc/loaded_driver_damping.py wifi reuse transceiver-adc-loaded-driver
