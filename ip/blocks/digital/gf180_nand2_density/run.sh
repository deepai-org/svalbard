#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label gf180-nand2-density \
  --source-rel ip/blocks/digital/gf180_nand2_density \
  --timeout 20m --cpus 4 --memory 6g \
  --copy result.json:gf180-nand2-density-last.json \
  --copy comparison.json:gf180-nand2-comparison-last.json \
  --copy physical-screen.json:gf180-nand2-physical-screen-last.json \
  --copy nand2-layout-comparison.png:gf180-nand2-layout-comparison-last.png
