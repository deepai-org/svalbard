#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label lane-rx-regenerative-frontend-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane_rx_regenerative_frontend/container_physical.sh \
  --timeout 60m --cpus 2 --memory 8g \
  --copy lane-rx-regenerative-frontend-physical.json:lane-rx-regenerative-frontend-physical-last.json \
  --copy lane-rx-regenerative-frontend.pex.spice:lane-rx-regenerative-frontend-last.pex.spice \
  --copy layout-lane-rx-regenerative-frontend.png:lane-rx-regenerative-frontend-layout-last.png
