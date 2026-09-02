#!/usr/bin/env bash
set -euo pipefail
python3 /src/event_lane_routed_parent/run_exact_pex.py \
  --pex /src/event_lane_routed_parent/event_lane_routed_parent.pex.spice \
  --physical /src/event_lane_routed_parent/physical_result.json \
  --environment-ids ff_cold ff_hot ss_cold \
  --work /src/event_lane_routed_parent/replay_logs --reuse-logs \
  --output /work/event_lane_routed_parent_exact_pex_remaining.json
