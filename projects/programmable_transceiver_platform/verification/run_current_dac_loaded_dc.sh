#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-loaded-dc dac/current_steering8_loaded_dc.py rf_references reuse transceiver-dac-current-dc
