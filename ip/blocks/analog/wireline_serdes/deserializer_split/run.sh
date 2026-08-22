#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-split-capture --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/deserializer_split/container_flow.sh --timeout 15m --cpus 4 --memory 8g \
  --copy result.json:serdes-split-capture-physical-last.json \
  --copy pex/deserializer_split_capture.pex.spice:serdes-split-capture-last.pex.spice \
  --copy deserializer-split-layout.png:serdes-split-capture-layout-last.png
