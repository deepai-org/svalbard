#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-capture dac/segmented8_capture_screen.py basic reuse transceiver-dac-segmented-registered
