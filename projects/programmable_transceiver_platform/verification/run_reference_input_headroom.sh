#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-input-headroom reference/input_headroom_screen.py basic reuse transceiver-reference-compensation
