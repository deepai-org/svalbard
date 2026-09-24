#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-interstage-autonomous quadrature/lo_interstage_autonomous.py autonomous_prepared fresh transceiver-lo-interstage-autonomous-prepared
