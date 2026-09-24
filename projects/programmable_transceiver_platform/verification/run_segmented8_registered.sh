#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-registered dac/segmented8_registered_screen.py basic reuse transceiver-dac-segmented-dynamic
