#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-full-duty-event-capture-explicit-delay-full \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_schematic.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy event-capture-result.json:pcie-full-duty-event-capture-explicit-delay-full-last.json \
  --copy retimed_capture_events.spice:pcie-full-duty-event-capture-explicit-delay-full-last.spice
