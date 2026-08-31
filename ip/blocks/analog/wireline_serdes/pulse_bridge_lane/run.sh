#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-pulse-bridge-regenerative-lane \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/pulse_bridge_lane/container_flow.sh --timeout 40m --cpus 2 --memory 8g \
  --copy pulse-physical.json:pulse-bridge-lane-pulse-physical-last.json \
  --copy result.json:pulse-bridge-regenerative-lane-last.json \
  --copy pulse-bridge-lane-pulse.pex.spice:pulse-bridge-lane-pulse-last.pex.spice
