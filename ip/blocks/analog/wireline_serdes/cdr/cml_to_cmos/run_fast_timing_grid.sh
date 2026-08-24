#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label cml-to-cmos-fast-timing-grid \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --command /src/cml_to_cmos/container_fast_timing_grid.sh \
  --timeout 15m --cpus 2 --memory 6g \
  --copy fast-grid-current.json:cml-to-cmos-fast-grid-current-last.json \
  --copy fast-grid-previous.json:cml-to-cmos-fast-grid-previous-last.json
