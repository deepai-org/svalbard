#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-pulse-generator-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_pulse_physical.sh \
  --timeout 45m --cpus 4 --memory 12g \
  --copy pulse-physical-smoke.json:clock-pulse-physical-smoke-last.json \
  --copy pulse-pex-result.json:clock-pulse-pex-last.json \
  --copy clock_pulse_generator-layout.png:clock-pulse-generator-layout-last.png \
  --copy clock_pulse_generator.pex.spice:clock-pulse-generator-last.pex.spice
