#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-capture-state-free-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_state_free_physical.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed_capture_events_admitted.spice:pcie-event-capture-state-free-admitted-last.spice \
  --copy retimed_event_capture_bridge.spice:pcie-event-capture-state-free-physical-last.spice \
  --copy retimed_event_capture_bridge.pex.spice:pcie-event-capture-state-free-pex-last.spice \
  --copy retimed-event-capture-physical.json:pcie-event-capture-state-free-physical-last.json \
  --copy pex-result.json:pcie-event-capture-state-free-pex-last.json \
  --copy lane-result.json:pcie-event-capture-state-free-lane-last.json \
  --copy lane-buffered-result.json:pcie-event-capture-state-free-lane-buffered-last.json \
  --copy retimed_event_capture_bridge-layout.png:pcie-event-capture-state-free-layout-last.png
