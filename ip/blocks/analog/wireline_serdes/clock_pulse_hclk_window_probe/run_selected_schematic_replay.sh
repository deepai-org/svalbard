#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-selected-dual-control-schematic-replay \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_selected_schematic_replay.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy selected-dual-control-schematic-replay.json:pcie-selected-dual-control-schematic-replay-last.json
