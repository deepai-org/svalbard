#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-lane-direct-sampler \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_event_lane_direct_sampler.sh \
  --timeout 30m --cpus 4 --memory 10g \
  --copy result.json:pcie-event-lane-direct-sampler-last.json
