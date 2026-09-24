#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-source-resistance tx/source_resistance.py wifi reuse transceiver-tx-buffered-lo
