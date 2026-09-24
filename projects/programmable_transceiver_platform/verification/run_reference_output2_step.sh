#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-output2-step reference/pair_hybrid_step.py paired_baseline fresh transceiver-reference-output2-impedance transceiver-reference-pair-hybrid-dc
