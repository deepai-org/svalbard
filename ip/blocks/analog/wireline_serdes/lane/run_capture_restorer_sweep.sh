#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-restorer-sweep \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_restorer_sweep.sh \
  --timeout 30m --cpus 4 --memory 14g \
  --copy capture-restorer-sweep.json:serdes-lane-capture-restorer-sweep-last.json \
  --copy capture-physical.json:serdes-lane-capture-restorer-sweep-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-restorer-sweep-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-restorer-sweep-layout-last.png
