#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-selfbias-ac quadrature/lo_selfbias_ac.py basic fresh
