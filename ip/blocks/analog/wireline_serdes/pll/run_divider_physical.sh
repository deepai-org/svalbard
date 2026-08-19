#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-divider-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 2 --memory 4g \
  --command /src/pll/container_divider_physical.sh \
  --copy divider-extracted-result.json:divider-extracted-result.json \
  --copy divider-physical-result.json:divider-physical-result.json \
  --copy divider.pex.spice:divider.pex.spice \
  --copy layout-divider.png:layout-divider.png
