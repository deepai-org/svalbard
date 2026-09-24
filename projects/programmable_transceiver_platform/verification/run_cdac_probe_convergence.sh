#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-cdac-probe-convergence adc/cdac_probe_convergence.py reference_probe fresh
