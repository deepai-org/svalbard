#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-lane-routed-parent-waveform-tt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/event_lane_routed_parent/container_waveform_tt.sh \
  --timeout 45m --cpus 4 --memory 16g \
  --copy event_lane_routed_parent_waveform_tt.json:pcie-event-lane-routed-parent-waveform-tt-last.json
