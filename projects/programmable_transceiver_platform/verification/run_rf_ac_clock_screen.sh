#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rf-ac-clock rf_ac_clock_screen.py rf_sources reuse
