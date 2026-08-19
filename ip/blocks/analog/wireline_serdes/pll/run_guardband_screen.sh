#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-guardband-screen \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 35m --cpus 2 --memory 4g --command /src/container_guardband_screen.sh \
  --copy guardband-screen.json:cml-vco-guardband-screen-last.json
