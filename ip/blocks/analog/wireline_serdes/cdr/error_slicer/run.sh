#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-error-slicer \
  --source-rel ip/blocks/analog/wireline_serdes/cdr/error_slicer \
  --timeout 45m --cpus 4 --memory 6g \
  --copy result.json:cdr-error-slicer-last.json \
  --copy schematic-pvt.json:cdr-error-slicer-schematic-last.json \
  --copy extracted-pvt.json:cdr-error-slicer-extracted-last.json \
  --copy cml_error_slicer-layout.png:cdr-error-slicer-layout-last.png \
  --copy cml_error_slicer.gds:cdr-error-slicer-last.gds \
  --copy pex/cml_error_slicer.pex.spice:cdr-error-slicer-last.pex.spice
