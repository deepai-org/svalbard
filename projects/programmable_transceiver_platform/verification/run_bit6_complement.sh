#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bit6-complement adc/bit6_complement_screen.py reference_frames fresh
