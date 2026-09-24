#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-ring-driven tx/ring_driven.py wifi reuse transceiver-tx-buffered-lo
