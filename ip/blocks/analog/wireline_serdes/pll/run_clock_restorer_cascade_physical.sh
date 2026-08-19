#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-clock-restorer-cascade-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 25m --cpus 2 --memory 4g \
  --command /src/pll/container_clock_restorer_cascade_physical.sh \
  --copy clock-restorer-cascade-physical-result.json:clock-restorer-cascade-physical-result.json \
  --copy clock-restorer-cascade.pex.spice:clock-restorer-cascade.pex.spice \
  --copy layout-clock-restorer-cascade.png:layout-clock-restorer-cascade.png
