#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-adc-shared-iq-receiver-cm adc/shared_iq_receiver_cm.py wifi reuse transceiver-adc-shared-iq-same
