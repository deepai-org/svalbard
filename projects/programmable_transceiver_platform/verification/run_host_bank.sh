#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-host-bank \
 --source-rel projects/programmable_transceiver_platform/verification \
 --timeout 5m --cpus 2 --memory 4g --command /src/screen_host_bank.py \
 --copy host-bank.json:transceiver-host-bank.json \
 --copy host-bank-waveforms.tar.gz:transceiver-host-bank-waveforms.tar.gz
