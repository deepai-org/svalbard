#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-shared-iq-preflight adc/shared_iq_screen.py wifi reuse transceiver-adc-sar8-reference-compensated
