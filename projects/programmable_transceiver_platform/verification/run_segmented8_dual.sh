#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-dual dac/segmented8_dual_screen.py basic reuse transceiver-dac-segmented-registered
