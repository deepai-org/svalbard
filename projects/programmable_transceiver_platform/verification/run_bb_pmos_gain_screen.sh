#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-pmos-gain bb_pmos_gain_screen.py
