#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-divider-restorer-full \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 60m --cpus 8 --memory 16g \
  --command /src/pll/container_vco_divider_restorer_full.sh \
  --copy vco-divider-restorer-full-result.json:vco-divider-restorer-full-result.json
