#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-step reference/pair_hybrid_step.py paired_baseline fresh transceiver-reference-hybrid-impedance transceiver-reference-pair-hybrid-dc
