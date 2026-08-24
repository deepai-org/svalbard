#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label cml-to-cmos-fast-probe \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --command /src/cml_to_cmos/container_fast_probe.sh \
  --timeout 10m --cpus 2 --memory 6g \
  --copy fast-probe.json:cml-to-cmos-fast-probe-last.json
