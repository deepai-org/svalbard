#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-impedance reference/pair_impedance_compare.py paired_inputs fresh transceiver-reference-pair-device-dc transceiver-reference-pair-long-mirror-dc
