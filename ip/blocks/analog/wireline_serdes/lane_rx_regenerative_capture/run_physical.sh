#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label lane-rx-regenerative-capture-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane_rx_regenerative_capture/container_physical.sh \
  --timeout 70m --cpus 2 --memory 10g \
  --copy lane-rx-regenerative-capture-physical.json:lane-rx-regenerative-capture-physical-last.json \
  --copy lane-rx-regenerative-capture.pex.spice:lane-rx-regenerative-capture-last.pex.spice \
  --copy layout-lane-rx-regenerative-capture.png:lane-rx-regenerative-capture-layout-last.png
