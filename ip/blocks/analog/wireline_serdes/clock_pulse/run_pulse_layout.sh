#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-pulse-generator-layout \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_pulse_layout.sh \
  --timeout 5m --cpus 2 --memory 4g \
  --copy pulse-layout-smoke.json:clock-pulse-layout-smoke-last.json \
  --copy clock_pulse_generator_layout.tcl:clock-pulse-layout-source-last.tcl \
  --copy clock_pulse_generator.gds:clock-pulse-generator-last.gds
