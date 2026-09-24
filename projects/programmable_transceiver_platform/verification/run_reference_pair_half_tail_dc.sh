#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-half-tail-dc reference/pair_half_tail_dc.py basic fresh
