#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-capture-state-free-full \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_state_free_full.sh \
  --timeout 20m --cpus 8 --memory 12g \
  --require-result-json result.json \
  --copy result.json:pcie-event-capture-state-free-full-last.json \
  --copy source.spice:pcie-event-capture-state-free-full-last.spice
