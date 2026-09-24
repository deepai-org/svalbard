#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-sar-driver-damping-400 adc/sar_command_replay.py prepared_replay fresh transceiver-sar-driver-damping-400-prepared
