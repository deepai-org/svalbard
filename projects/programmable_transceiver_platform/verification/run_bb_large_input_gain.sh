#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-large-input-gain baseband/large_input_gain.py basic fresh
