#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-long-mirror-frames adc/reference_long_mirror_screen.py reference_frames fresh
