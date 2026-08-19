#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-cap-drc \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 15m --cpus 2 --memory 4g --command /src/container_cap_drc.sh \
  --copy cap-drc.json:cml-vco-cap-drc-last.json
