#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-extracted-2p5-pvt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_extracted_2p5_pvt.sh \
  --timeout 40m --cpus 4 --memory 14g \
  --copy pvt-2p5.json:serdes-lane-extracted-2p5-pvt-last.json \
  --copy pvt-2p5-tt.json:serdes-lane-extracted-2p5-pvt-tt-last.json \
  --copy pvt-2p5-ff_cold.json:serdes-lane-extracted-2p5-pvt-ff-cold-last.json \
  --copy pvt-2p5-ff_hot.json:serdes-lane-extracted-2p5-pvt-ff-hot-last.json \
  --copy pvt-2p5-ss_hot.json:serdes-lane-extracted-2p5-pvt-ss-hot-last.json \
  --copy pvt-2p5-ss_passive.json:serdes-lane-extracted-2p5-pvt-ss-passive-last.json
