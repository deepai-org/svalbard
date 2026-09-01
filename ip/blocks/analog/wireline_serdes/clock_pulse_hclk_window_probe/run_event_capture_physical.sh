#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-full-duty-event-capture-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_physical.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed-event-capture-physical.json:pcie-full-duty-event-capture-physical-last.json \
  --copy retimed-event-capture-pex-result.json:pcie-full-duty-event-capture-pex-target-last.json \
  --copy retimed_event_capture_bridge.pex.spice:pcie-full-duty-event-capture-physical-last.pex.spice \
  --copy retimed_event_capture_bridge.spice:pcie-full-duty-event-capture-physical-last.spice \
  --copy retimed_event_capture_bridge-layout.png:pcie-full-duty-event-capture-physical-last.png
