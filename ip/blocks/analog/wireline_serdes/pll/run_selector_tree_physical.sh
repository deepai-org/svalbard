#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-selector-tree-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 40m --cpus 2 --memory 4g --command /src/pll/container_selector_tree_physical.sh \
  --copy selector-tree-physical-result.json:cml-vco-selector-tree-physical-last.json \
  --copy vco-selector-tree.pex.spice:cml-vco-selector-tree-pex-last.spice \
  --copy vco-selector-tree-layout.png:cml-vco-selector-tree-layout-last.png
