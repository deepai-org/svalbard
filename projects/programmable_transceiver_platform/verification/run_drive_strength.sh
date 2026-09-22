#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-drive-strength \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_drive_strength.sh \
 --copy drive-strength.json:transceiver-drive-strength.json \
 --copy drive-strength-waveforms.tar.gz:transceiver-drive-strength-waveforms.tar.gz
