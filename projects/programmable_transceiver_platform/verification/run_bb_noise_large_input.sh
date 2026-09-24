#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-noise-large-input baseband/noise_large_input.py basic fresh
