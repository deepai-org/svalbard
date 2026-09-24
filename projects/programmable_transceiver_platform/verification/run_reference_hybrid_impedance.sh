#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-impedance reference/pair_hybrid_impedance.py paired_inputs fresh transceiver-reference-pair-device-dc transceiver-reference-pair-hybrid-dc
