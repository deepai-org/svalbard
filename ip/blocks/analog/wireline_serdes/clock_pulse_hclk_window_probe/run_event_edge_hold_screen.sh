#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-edge-hold-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_edge_hold_screen.sh \
  --timeout 20m --cpus 8 --memory 12g \
  --copy edge-hold-screen.json:pcie-event-edge-hold-screen-last.json
