#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-pulse-ff-cold-load-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/pulse_bridge_lane/container_ff_cold_load_probe.sh \
  --timeout 25m --cpus 2 --memory 8g \
  --copy pulse-physical.json:pulse-ff-cold-load-probe-physical-last.json \
  --copy load-probe-result.json:pulse-ff-cold-load-probe-last.json
