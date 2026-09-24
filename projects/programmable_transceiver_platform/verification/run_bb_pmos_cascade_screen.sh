#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-pmos-cascade bb_pmos_cascade_screen.py
