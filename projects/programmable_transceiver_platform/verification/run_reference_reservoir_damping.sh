#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-reservoir-damping reference/reservoir_damping_screen.py rf_references reuse transceiver-reference-driver-impedance
