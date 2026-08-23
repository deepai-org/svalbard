#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-rx-bias-sweep --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_rx_bias_sweep.sh --timeout 30m --cpus 4 --memory 14g \
  --copy capture-rx-bias-sweep.json:serdes-lane-capture-rx-bias-sweep-last.json \
  --copy capture-physical.json:serdes-lane-capture-rx-bias-sweep-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-rx-bias-sweep-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-rx-bias-sweep-layout-last.png
