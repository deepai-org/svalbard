#!/usr/bin/env bash
set -euo pipefail

/src/pll/container_selector_tree_physical.sh
python3 /src/pll/run_selector_tree.py --source /src/pll \
  --pex /work/vco-selector-tree.pex.spice --work /work/tree-sim \
  --output /work/selector-tree-simulation-result.json
python3 /src/pll/check_selector_tree.py \
  --physical /work/selector-tree-physical-result.json \
  --simulation /work/selector-tree-simulation-result.json \
  --output /work/selector-tree-result.json
