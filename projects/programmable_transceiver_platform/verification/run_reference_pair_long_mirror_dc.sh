#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-long-mirror-dc reference/pair_long_mirror_dc.py basic fresh
