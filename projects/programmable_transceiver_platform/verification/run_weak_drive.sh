#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-weak-drive \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_weak_drive.sh \
 --copy weak-drive.json:transceiver-weak-drive.json \
 --copy weak-drive-waveforms.tar.gz:transceiver-weak-drive-waveforms.tar.gz
