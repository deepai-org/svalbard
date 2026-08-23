#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-capture \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_capture.sh \
  --timeout 60m --cpus 2 --memory 10g \
  --copy capture-2p5-rxcap.json:serdes-lane-capture-2p5-rx-capture-last.json \
  --copy capture-2p5-rxcap-tt.json:serdes-lane-capture-2p5-rx-capture-tt-last.json \
  --copy capture-2p5-rxcap-ff_cold.json:serdes-lane-capture-2p5-rx-capture-ff-cold-last.json \
  --copy capture-2p5-rxcap-ff_hot.json:serdes-lane-capture-2p5-rx-capture-ff-hot-last.json \
  --copy capture-2p5-rxcap-ss_hot.json:serdes-lane-capture-2p5-rx-capture-ss-hot-last.json \
  --copy capture-2p5-rxcap-ss_passive.json:serdes-lane-capture-2p5-rx-capture-ss-passive-last.json
