#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-bandwidth-mode --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_bandwidth_mode.sh --timeout 30m --cpus 4 --memory 14g \
  --copy capture-bandwidth-mode.json:serdes-lane-capture-bandwidth-mode-last.json \
  --copy capture-physical.json:serdes-lane-capture-bandwidth-mode-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-bandwidth-mode-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-bandwidth-mode-layout-last.png
