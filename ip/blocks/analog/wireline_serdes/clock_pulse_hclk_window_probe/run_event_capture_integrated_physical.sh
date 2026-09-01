#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-capture-integrated-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_capture_integrated_physical.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --require-result-json pex-result.json \
  --copy retimed-event-capture-physical.json:pcie-event-capture-integrated-physical-last.json \
  --copy pex-result.json:pcie-event-capture-integrated-pex-last.json \
  --copy pex-probe-result.json:pcie-event-capture-integrated-pex-probe-last.json \
  --copy retimed_event_capture_bridge.pex.spice:pcie-event-capture-integrated-last.pex.spice \
  --copy retimed_event_capture_bridge.spice:pcie-event-capture-integrated-last.spice \
  --copy retimed_event_capture_bridge-layout.png:pcie-event-capture-integrated-last.png
