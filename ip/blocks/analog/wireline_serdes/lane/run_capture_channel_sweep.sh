#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-channel-sweep --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_channel_sweep.sh --timeout 30m --cpus 4 --memory 14g \
  --copy capture-channel-sweep.json:serdes-lane-capture-channel-sweep-last.json \
  --copy capture-physical.json:serdes-lane-capture-channel-sweep-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-channel-sweep-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-channel-sweep-layout-last.png
