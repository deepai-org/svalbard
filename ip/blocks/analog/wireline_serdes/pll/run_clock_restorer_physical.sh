#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-clock-restorer-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 20m --cpus 2 --memory 4g \
  --command /src/pll/container_clock_restorer_physical.sh \
  --copy clock-restorer-physical-result.json:clock-restorer-physical-result.json \
  --copy clock-restorer.pex.spice:clock-restorer.pex.spice \
  --copy layout-clock-restorer.png:layout-clock-restorer.png
