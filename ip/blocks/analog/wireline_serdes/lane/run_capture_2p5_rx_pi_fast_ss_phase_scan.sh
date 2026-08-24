#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"

copies=(--copy ss-phase-scan.json:ss-phase-scan-last.json)
for phase in 45 225 270 315; do
  copies+=(--copy "ss-phase-${phase}.json:ss-phase-${phase}-last.json")
done

exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-ss-phase-scan \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_ss_phase_scan.sh \
  --timeout 70m --cpus 2 --memory 10g "${copies[@]}"
