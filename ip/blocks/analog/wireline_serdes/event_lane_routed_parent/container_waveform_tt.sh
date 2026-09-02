#!/usr/bin/env bash
set -euo pipefail
python3 /src/event_lane_routed_parent/run_dynamic_pex.py \
  --pex /src/event_lane_routed_parent/event_lane_routed_parent.pex.spice \
  --physical /src/event_lane_routed_parent/physical_result.json \
  --environment-id tt --sample-count 4 --waveform-step-ps 10 \
  --work /work/waveform-tt --allow-fail \
  --output /work/event_lane_routed_parent_waveform_tt.json
