#!/usr/bin/env bash
set -euo pipefail

/src/pll/container_selector_tree_physical.sh
python3 /src/pll/screen_selector_tree_gain.py --source /src/pll \
  --pex /work/vco-selector-tree.pex.spice --work /work/tree-gain-screen \
  --output /work/selector-tree-gain-screen.json
