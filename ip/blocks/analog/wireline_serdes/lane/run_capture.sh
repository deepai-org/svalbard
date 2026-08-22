#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture.sh --timeout 25m --cpus 4 --memory 12g \
  --copy capture.json:serdes-lane-capture-last.json \
  --copy capture-pvt.json:serdes-lane-capture-pvt-last.json \
  --copy capture-physical.json:serdes-lane-capture-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-layout-last.png
