#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-clock-boundary-compare \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_clock_boundary_compare.sh \
  --timeout 30m --cpus 2 --memory 10g \
  --copy ideal.json:serdes-lane-capture-ideal-clock-last.json \
  --copy pi.json:serdes-lane-capture-pi-clock-last.json \
  --copy ideal-clock.log:serdes-lane-capture-ideal-clock-last.log \
  --copy pi-clock.log:serdes-lane-capture-pi-clock-last.log
