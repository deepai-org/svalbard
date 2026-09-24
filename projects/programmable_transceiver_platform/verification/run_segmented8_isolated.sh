#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-isolated dac/segmented8_isolated_screen.py basic reuse transceiver-dac-segmented-registered
