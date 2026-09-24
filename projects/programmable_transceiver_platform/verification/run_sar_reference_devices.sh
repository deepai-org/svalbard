#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-sar-reference-devices adc/sar_command_replay.py prepared_replay fresh transceiver-sar-reference-devices-prepared
