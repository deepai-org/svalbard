#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label lane-rx-pi-capture-fast-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane_rx_pi_capture/container_fast_physical.sh \
  --timeout 70m --cpus 2 --memory 10g \
  --copy lane-rx-pi-capture-fast-physical.json:lane-rx-pi-capture-fast-physical.json \
  --copy lane-rx-pi-capture-fast.pex.spice:lane-rx-pi-capture-fast.pex.spice \
  --copy layout-lane-rx-pi-capture-fast.png:lane-rx-pi-capture-fast-layout.png
