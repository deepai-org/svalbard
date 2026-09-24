#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-receiver-driver-probe adc/receiver_driver_probe.py wifi reuse transceiver-adc-shared-iq-receiver-cm
