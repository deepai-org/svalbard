#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-selected-dual-control-pulse-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_selected_physical.sh \
  --timeout 45m --cpus 8 --memory 16g \
  --copy selected-dual-control-physical.json:pcie-selected-dual-control-physical-last.json \
  --copy selected-dual-control-pex.json:pcie-selected-dual-control-pex-last.json \
  --copy selected_dual_control_pulse.pex.spice:pcie-selected-dual-control-last.pex.spice \
  --copy selected_dual_control_pulse-layout.png:pcie-selected-dual-control-layout-last.png \
  --copy drc-stage.log:pcie-selected-dual-control-drc-last.log \
  --copy lvs-stage.log:pcie-selected-dual-control-lvs-last.log
