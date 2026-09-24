#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-loaded-driver adc/loaded_driver_screen.py wifi reuse
