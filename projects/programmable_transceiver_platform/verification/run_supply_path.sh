#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-supply-path \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_supply_path.sh \
 --copy supply-path.json:transceiver-supply-path.json \
 --copy supply-path-waveforms.tar.gz:transceiver-supply-path-waveforms.tar.gz
