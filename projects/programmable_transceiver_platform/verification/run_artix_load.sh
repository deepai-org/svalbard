#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
# This characterization may expose design failures; it is not a pass/fail signoff report.
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-artix-load \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_artix_load.sh \
 --copy artix-load.json:transceiver-artix-load.json \
 --copy artix-load-waveforms.tar.gz:transceiver-artix-load-waveforms.tar.gz
