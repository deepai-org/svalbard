#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label cml-to-cmos-fast-physical \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --command /src/cml_to_cmos/container_fast_physical.sh \
  --timeout 30m --cpus 2 --memory 8g \
  --copy cml_to_cmos-fast-physical.json:cml_to_cmos-fast-physical.json \
  --copy cml_to_cmos-fast.pex.spice:cml_to_cmos-fast.pex.spice \
  --copy fast-extracted.json:cml_to_cmos-fast-extracted.json \
  --copy cml_to_cmos-fast-layout.png:cml_to_cmos-fast-layout.png
