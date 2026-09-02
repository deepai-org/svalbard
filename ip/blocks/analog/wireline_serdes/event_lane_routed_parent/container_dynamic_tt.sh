#!/usr/bin/env bash
set -euo pipefail
python3 /src/event_lane_routed_parent/run_dynamic_pex.py \
  --pex /src/event_lane_routed_parent/event_lane_routed_parent.pex.spice \
  --physical /src/event_lane_routed_parent/physical_result.json \
  --environment-id tt --sample-count 10 --work /work/dynamic-tt \
  --allow-fail --output /work/event_lane_routed_parent_dynamic_tt.json
