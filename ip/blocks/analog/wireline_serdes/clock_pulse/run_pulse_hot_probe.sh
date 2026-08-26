#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-pulse-hot-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_pulse_hot_probe.sh \
  --timeout 20m --cpus 2 --memory 8g \
  --copy pulse-hot-probe-smoke.json:clock-pulse-hot-probe-smoke-last.json \
  --copy pulse-pex-nominal-result.json:clock-pulse-hot-probe-nominal-last.json \
  --copy pulse-hot-probe-result.json:clock-pulse-hot-probe-last.json \
  --copy clock_pulse_generator-layout.png:clock-pulse-hot-probe-layout-last.png \
  --copy clock_pulse_generator.pex.spice:clock-pulse-hot-probe-last.pex.spice
