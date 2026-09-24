#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-selfbias-dynamic tx/selfbias_dynamic.py measured_lo reuse
