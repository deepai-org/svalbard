#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-dynamic dac/current_steering8_dynamic.py rf_references reuse transceiver-dac-loaded-dc
