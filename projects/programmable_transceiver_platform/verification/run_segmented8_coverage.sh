#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-coverage dac/segmented8_registered_coverage.py basic reuse transceiver-dac-segmented-dynamic
