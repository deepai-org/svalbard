#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-shared-iq-frames adc/shared_iq_frames.py wifi reuse transceiver-adc-shared-iq-preflight
