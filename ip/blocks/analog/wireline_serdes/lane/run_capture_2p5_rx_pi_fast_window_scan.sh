#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"

copies=(--copy ss-window-scan.json:ss-window-scan-last.json)
for tag in d400_w380 d450_w320 d450_w350 d500_w270 d500_w300 d550_w220; do
  copies+=(--copy "ss-window-${tag}.json:ss-window-${tag}-last.json")
done

exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-window-scan \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_window_scan.sh \
  --timeout 90m --cpus 2 --memory 10g "${copies[@]}"
