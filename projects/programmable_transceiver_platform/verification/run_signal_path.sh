#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-signal-path \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_signal_path.sh \
 --copy signal-path.json:transceiver-signal-path.json \
 --copy signal-path-waveforms.tar.gz:transceiver-signal-path-waveforms.tar.gz
