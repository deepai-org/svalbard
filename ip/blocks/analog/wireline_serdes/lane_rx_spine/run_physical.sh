#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label lane-rx-spine-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 35m --cpus 2 --memory 8g \
  --command /src/lane_rx_spine/container_physical.sh \
  --copy lane-rx-spine-physical-result.json:lane-rx-spine-physical-result.json \
  --copy lane-rx-spine.pex.spice:lane-rx-spine.pex.spice \
  --copy layout-lane-rx-spine.png:layout-lane-rx-spine.png
