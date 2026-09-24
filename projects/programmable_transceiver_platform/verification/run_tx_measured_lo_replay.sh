#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-measured-lo-replay tx/measured_lo_replay.py measured_lo reuse
