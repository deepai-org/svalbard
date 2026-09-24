#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-rf-only quadrature/lo_interstage_autonomous.py autonomous_prepared fresh transceiver-lo-rf-only-prepared
