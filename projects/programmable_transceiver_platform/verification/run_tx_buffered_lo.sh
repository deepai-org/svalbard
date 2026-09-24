#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-buffered-lo tx/buffered_lo.py wifi reuse transceiver-tx-lo-switching
