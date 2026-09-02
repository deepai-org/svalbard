#!/bin/bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-start-end-sr-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_start_end_sr_physical.sh \
  --timeout 20m --cpus 8 --memory 12g \
  --copy retimed_event_capture_bridge.spice:pcie-event-start-end-sr-physical-last.spice \
  --copy retimed_event_capture_bridge.pex.spice:pcie-event-start-end-sr-pex-last.spice \
  --copy retimed-event-capture-start-end-sr-physical.json:pcie-event-start-end-sr-physical-last.json \
  --copy lane-result.json:pcie-event-start-end-sr-lane-last.json \
  --copy retimed_event_capture_bridge-layout.png:pcie-event-start-end-sr-layout-last.png
