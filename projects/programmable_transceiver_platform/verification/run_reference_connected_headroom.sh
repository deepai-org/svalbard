#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-connected-headroom reference/connected_headroom_screen.py rf_references reuse transceiver-adc-sar8-reference-compensated
