#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-frontend \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_frontend.sh \
  --timeout 60m --cpus 2 --memory 10g \
  --copy capture-2p5-front.json:serdes-lane-capture-2p5-rx-frontend-last.json \
  --copy capture-2p5-front-tt.json:serdes-lane-capture-2p5-rx-frontend-tt-last.json \
  --copy capture-2p5-front-ff_cold.json:serdes-lane-capture-2p5-rx-frontend-ff-cold-last.json \
  --copy capture-2p5-front-ff_hot.json:serdes-lane-capture-2p5-rx-frontend-ff-hot-last.json \
  --copy capture-2p5-front-ss_hot.json:serdes-lane-capture-2p5-rx-frontend-ss-hot-last.json \
  --copy capture-2p5-front-ss_passive.json:serdes-lane-capture-2p5-rx-frontend-ss-passive-last.json
