#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-bias-restoration quadrature/lo_receiver_replay.py named_replay fresh transceiver-lo-bias-restoration-prepared
