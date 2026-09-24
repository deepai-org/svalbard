#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-sar-reservoir-full adc/sar_command_replay.py prepared_replay fresh transceiver-sar-reservoir-full-prepared
