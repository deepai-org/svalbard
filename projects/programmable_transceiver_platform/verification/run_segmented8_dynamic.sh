#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-dac-segmented-dynamic dac/segmented8_dynamic.py basic reuse transceiver-dac-segmented-dc
