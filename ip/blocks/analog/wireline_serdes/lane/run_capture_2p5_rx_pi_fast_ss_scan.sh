#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"

copies=(--copy ss-even-skew-scan.json:ss-even-skew-scan-last.json)
for tag in m150 m050 p050 p150 p250 p350 p450; do
  copies+=(--copy "ss-even-skew-${tag}.json:ss-even-skew-${tag}-last.json")
done

exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-ss-scan \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_ss_scan.sh \
  --timeout 90m --cpus 2 --memory 10g "${copies[@]}"
