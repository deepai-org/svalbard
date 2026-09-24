#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-target-dc-v2 reference/pair_target_dc.py basic fresh
