#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-reference-current adc/reference_current_replay.py wifi reuse transceiver-adc-reference-current-prepared
