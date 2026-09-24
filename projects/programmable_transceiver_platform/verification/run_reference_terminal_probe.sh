#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-terminal-probe adc/sar_command_replay.py prepared_replay fresh transceiver-reference-terminal-probe-prepared
