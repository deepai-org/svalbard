#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-connected-current reference/connected_current_screen.py rf_references reuse transceiver-reference-connected-headroom
