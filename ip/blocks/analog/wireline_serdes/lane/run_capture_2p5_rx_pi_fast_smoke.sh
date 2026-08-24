#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-rx-pi-fast-smoke \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_rx_pi_fast_smoke.sh \
  --timeout 30m --cpus 2 --memory 10g \
  --copy capture-2p5-rx-pi-fast-tt.json:serdes-lane-capture-2p5-rx-pi-fast-smoke-last.json
