#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-cdac-probe-reltol adc/cdac_probe_reltol.py reference_probe fresh
