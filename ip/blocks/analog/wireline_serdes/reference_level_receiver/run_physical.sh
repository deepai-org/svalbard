#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" --label serdes-reference-level-receiver-physical --source-rel ip/blocks/analog/wireline_serdes --command /src/reference_level_receiver/container_physical.sh --timeout 40m --cpus 2 --memory 8g --copy physical.json:serdes-reference-level-receiver-physical-last.json --copy extracted.json:serdes-reference-level-receiver-extracted-last.json --copy reference_level_receiver.pex.spice:serdes-reference-level-receiver-last.pex.spice --copy reference-level-receiver-layout.png:serdes-reference-level-receiver-layout-last.png
