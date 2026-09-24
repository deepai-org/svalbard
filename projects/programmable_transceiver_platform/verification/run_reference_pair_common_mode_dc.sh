#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-common-mode-dc reference/pair_common_mode_dc.py basic fresh
