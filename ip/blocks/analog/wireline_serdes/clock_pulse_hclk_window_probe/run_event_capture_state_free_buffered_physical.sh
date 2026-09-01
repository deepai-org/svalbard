#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-capture-state-free-buffered-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_state_free_buffered_physical.sh \
  --timeout 20m --cpus 8 --memory 12g \
  --copy retimed_event_capture_bridge.spice:pcie-event-capture-state-free-buffered-physical-last.spice \
  --copy retimed_event_capture_bridge.pex.spice:pcie-event-capture-state-free-buffered-pex-last.spice \
  --copy retimed-event-capture-buffered-physical.json:pcie-event-capture-state-free-buffered-physical-last.json \
  --copy lane-result.json:pcie-event-capture-state-free-buffered-lane-last.json \
  --copy retimed_event_capture_bridge-layout.png:pcie-event-capture-state-free-buffered-layout-last.png
