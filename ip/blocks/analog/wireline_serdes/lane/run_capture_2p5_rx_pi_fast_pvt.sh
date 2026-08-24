#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-pvt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_pvt.sh \
  --timeout 90m --cpus 2 --memory 10g \
  --copy capture-2p5-rx-pi-fast.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-last.json \
  --copy capture-2p5-rx-pi-fast-tt.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-tt-last.json \
  --copy capture-2p5-rx-pi-fast-ff_cold.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-ff-cold-last.json \
  --copy capture-2p5-rx-pi-fast-ff_hot.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-ff-hot-last.json \
  --copy capture-2p5-rx-pi-fast-ss_hot.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-ss-hot-last.json \
  --copy capture-2p5-rx-pi-fast-ss_passive.json:serdes-lane-capture-2p5-rx-pi-fast-pvt-ss-passive-last.json
