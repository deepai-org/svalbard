#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-phase-error-filter \
  --source-rel ip/blocks/analog/wireline_serdes/cdr/phase_error_filter \
  --timeout 30m --cpus 4 --memory 6g \
  --copy result.json:cdr-phase-error-filter-last.json \
  --copy schematic-pvt.json:cdr-phase-error-filter-schematic-last.json \
  --copy extracted-pvt.json:cdr-phase-error-filter-extracted-last.json \
  --copy cml_phase_error_filter-layout.png:cdr-phase-error-filter-layout-last.png \
  --copy cml_phase_error_filter.gds:cdr-phase-error-filter-last.gds \
  --copy pex/cml_phase_error_filter.pex.spice:cdr-phase-error-filter-last.pex.spice
