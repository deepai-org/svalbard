#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-selector-tree \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 60m --cpus 2 --memory 4g --command /src/pll/container_selector_tree.sh \
  --copy selector-tree-result.json:cml-vco-selector-tree-last.json \
  --copy selector-tree-simulation-result.json:cml-vco-selector-tree-simulation-last.json \
  --copy vco-selector-tree-layout.png:cml-vco-selector-tree-layout-last.png
