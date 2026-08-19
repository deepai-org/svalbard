#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-selector-tree-gain-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 35m --cpus 2 --memory 4g \
  --command /src/pll/container_selector_tree_gain_screen.sh \
  --copy selector-tree-gain-screen.json:cml-vco-selector-tree-gain-screen-last.json
