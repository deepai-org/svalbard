#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pfd-offset pll/pfd_offset_screen.py basic reuse transceiver-pfd-buffered-reference
