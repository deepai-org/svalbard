#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label lane-rx-capture-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 55m --cpus 2 --memory 10g \
  --command /src/lane_rx_capture/container_physical.sh \
  --copy lane-rx-capture-physical-result.json:lane-rx-capture-physical-result.json \
  --copy lane-rx-capture.pex.spice:lane-rx-capture.pex.spice \
  --copy layout-lane-rx-capture.png:layout-lane-rx-capture.png
