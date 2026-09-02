#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-local-clock-fanout-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_local_clock_fanout_physical.sh \
  --timeout 20m --cpus 4 --memory 10g \
  --copy local_clock_fanout.spice:pcie-local-clock-fanout-last.spice \
  --copy local_clock_fanout.pex.spice:pcie-local-clock-fanout-last.pex.spice \
  --copy local-clock-fanout-physical.json:pcie-local-clock-fanout-physical-last.json \
  --copy local_clock_fanout-layout.png:pcie-local-clock-fanout-layout-last.png
