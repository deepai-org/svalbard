#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-frames adc/reference_hybrid_screen.py reference_frames fresh
