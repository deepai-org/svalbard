#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label lane-rx-pi-capture-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 60m --cpus 2 --memory 10g \
  --command /src/lane_rx_pi_capture/container_physical.sh \
  --copy lane-rx-pi-capture-physical-result.json:lane-rx-pi-capture-physical-result.json \
  --copy lane-rx-pi-capture.pex.spice:lane-rx-pi-capture.pex.spice \
  --copy layout-lane-rx-pi-capture.png:layout-lane-rx-pi-capture.png
