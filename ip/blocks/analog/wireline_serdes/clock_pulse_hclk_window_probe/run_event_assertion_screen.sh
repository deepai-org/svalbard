#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-assertion-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_assertion_screen.sh \
  --timeout 20m --cpus 8 --memory 12g \
  --copy assertion-screen.json:pcie-event-assertion-screen-last.json
