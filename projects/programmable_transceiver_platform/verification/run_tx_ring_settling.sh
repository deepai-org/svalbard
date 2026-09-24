#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-ring-settling tx/ring_settling.py wifi reuse transceiver-tx-startup-state
