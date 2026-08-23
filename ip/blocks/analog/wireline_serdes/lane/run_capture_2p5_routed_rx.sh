#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-routed-rx \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_routed_rx.sh \
  --timeout 60m --cpus 2 --memory 8g \
  --copy capture-2p5-routed.json:serdes-lane-capture-2p5-routed-rx-last.json \
  --copy capture-2p5-routed-tt.json:serdes-lane-capture-2p5-routed-rx-tt-last.json \
  --copy capture-2p5-routed-ff_cold.json:serdes-lane-capture-2p5-routed-rx-ff-cold-last.json \
  --copy capture-2p5-routed-ff_hot.json:serdes-lane-capture-2p5-routed-rx-ff-hot-last.json \
  --copy capture-2p5-routed-ss_hot.json:serdes-lane-capture-2p5-routed-rx-ss-hot-last.json \
  --copy capture-2p5-routed-ss_passive.json:serdes-lane-capture-2p5-routed-rx-ss-passive-last.json
