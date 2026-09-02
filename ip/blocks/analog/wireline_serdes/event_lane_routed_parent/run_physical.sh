#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-lane-routed-parent \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/event_lane_routed_parent/container_physical.sh \
  --timeout 45m --cpus 4 --memory 16g \
  --copy event_lane_routed_parent.spice:pcie-event-lane-routed-parent-last.spice \
  --copy event_lane_routed_parent.pex.spice:pcie-event-lane-routed-parent-last.pex.spice \
  --copy event_lane_routed_parent_physical.json:pcie-event-lane-routed-parent-physical-last.json \
  --copy event_lane_routed_parent-layout.png:pcie-event-lane-routed-parent-layout-last.png
