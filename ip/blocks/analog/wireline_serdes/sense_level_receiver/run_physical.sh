#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-sense-level-receiver-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/sense_level_receiver/container_physical.sh \
  --timeout 45m --cpus 2 --memory 8g \
  --copy physical.json:serdes-sense-level-receiver-physical-last.json \
  --copy leaf-result.json:serdes-sense-level-receiver-leaf-last.json \
  --copy consumer-result.json:serdes-sense-level-receiver-consumer-last.json \
  --copy control-plan.json:serdes-sense-level-receiver-controls-last.json \
  --copy sense_level_receiver.pex.spice:serdes-sense-level-receiver-last.pex.spice \
  --copy sense_level_receiver.spice:serdes-sense-level-receiver-last.spice \
  --copy variant_manifest.json:serdes-sense-level-receiver-variant-last.json \
  --copy reference-level-receiver-layout.png:serdes-sense-level-receiver-layout-last.png
