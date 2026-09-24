#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-sampled-comparator adc/sampled_comparator_screen.py rf_references
