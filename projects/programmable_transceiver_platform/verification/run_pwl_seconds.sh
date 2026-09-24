#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pwl-seconds pll/pwl_seconds_screen.py basic reuse transceiver-pfd-buffered-reference
