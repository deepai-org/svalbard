#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-replay-sensitivity tx/replay_sensitivity.py wifi reuse transceiver-tx-measured-lo-replay
