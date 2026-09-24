#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-selfbias-sine quadrature/lo_selfbias_sine.py basic fresh
