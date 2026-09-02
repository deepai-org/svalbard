#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_parent_waveform_replay.py \
  --parent-result /src/event_lane_routed_parent/waveform_tt_result.json \
  --pex /src/reference_level_receiver/reference_level_receiver.pex.spice \
  --consumer-pex /src/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice \
  --work /work/replay --allow-fail --output /work/result.json
