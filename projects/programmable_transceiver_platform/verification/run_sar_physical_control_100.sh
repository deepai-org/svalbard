#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-sar-physical-control-100 adc/sar_command_replay.py prepared_replay fresh transceiver-sar-physical-control-100-prepared
