#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"

copies=(--copy ss-hot-skew-scan.json:ss-hot-skew-scan-last.json)
for skew in 300 350 400 450; do
  copies+=(--copy "ss-hot-skew-${skew}.json:ss-hot-skew-${skew}-last.json")
done

exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-ss-hot-scan \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_ss_hot_scan.sh \
  --timeout 70m --cpus 2 --memory 10g "${copies[@]}"
