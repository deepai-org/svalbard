#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-step reference/pair_step_screen.py paired_baseline fresh transceiver-reference-pair-impedance transceiver-reference-pair-long-mirror-dc
