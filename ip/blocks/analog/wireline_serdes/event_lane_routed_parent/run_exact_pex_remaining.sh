#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-lane-routed-parent-exact-pex-remaining \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/event_lane_routed_parent/container_exact_pex_remaining.sh \
  --timeout 60m --cpus 4 --memory 16g \
  --copy event_lane_routed_parent_exact_pex_remaining.json:pcie-event-lane-routed-parent-exact-pex-remaining-last.json
