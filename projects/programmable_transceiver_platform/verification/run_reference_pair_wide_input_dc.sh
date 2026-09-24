#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-wide-input-dc reference/pair_wide_input_dc.py basic fresh
