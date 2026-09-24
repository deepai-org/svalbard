#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-load-tolerance reference/pair_hybrid_load_tolerance.py paired_inputs fresh transceiver-reference-pair-device-dc transceiver-reference-pair-hybrid-dc
