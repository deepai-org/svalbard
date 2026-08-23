#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label lane-rx-frontend-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 45m --cpus 2 --memory 10g \
  --command /src/lane_rx_frontend/container_physical.sh \
  --copy lane-rx-frontend-physical-result.json:lane-rx-frontend-physical-result.json \
  --copy lane-rx-frontend.pex.spice:lane-rx-frontend.pex.spice \
  --copy layout-lane-rx-frontend.png:layout-lane-rx-frontend.png
