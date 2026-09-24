#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-cdac-probe-startup adc/cdac_probe_startup.py reference_probe fresh
