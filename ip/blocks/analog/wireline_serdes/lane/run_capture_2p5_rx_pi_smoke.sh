#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-smoke \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_smoke.sh \
  --timeout 30m --cpus 2 --memory 10g \
  --copy rx-pi-smoke.json:serdes-lane-capture-2p5-rx-pi-smoke-last.json \
  --copy rx-pi-smoke-convert-200p.log:serdes-lane-capture-2p5-rx-pi-smoke-last.log
