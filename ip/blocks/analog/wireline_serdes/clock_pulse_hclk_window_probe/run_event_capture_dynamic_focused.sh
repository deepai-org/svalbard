#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-capture-dynamic-focused \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_dynamic_focused.sh \
  --timeout 20m --cpus 4 --memory 8g \
  --copy result.json:pcie-event-capture-dynamic-focused-last.json \
  --copy source.spice:pcie-event-capture-dynamic-focused-last.spice
