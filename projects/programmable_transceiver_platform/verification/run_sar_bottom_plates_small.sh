#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-sar-bottom-plates-small adc/sar_command_replay.py prepared_replay fresh transceiver-sar-bottom-plates-small-prepared
