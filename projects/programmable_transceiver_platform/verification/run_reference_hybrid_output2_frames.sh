#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-hybrid-output2-frames adc/reference_hybrid_output2_screen.py reference_frames fresh
