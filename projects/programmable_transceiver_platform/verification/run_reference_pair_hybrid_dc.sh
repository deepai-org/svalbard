#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-hybrid-dc reference/pair_hybrid_dc.py basic fresh
