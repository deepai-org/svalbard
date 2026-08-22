#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-stress --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_stress.sh --timeout 35m --cpus 4 --memory 14g \
  --copy capture-stress.json:serdes-lane-capture-stress-last.json \
  --copy capture-physical.json:serdes-lane-capture-stress-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-stress-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-stress-layout-last.png
