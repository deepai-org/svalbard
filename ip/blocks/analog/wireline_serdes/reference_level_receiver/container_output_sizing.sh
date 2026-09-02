#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_output_sizing.py \
  --source /src/reference_level_receiver/reference_level_receiver.spice \
  --parent-result /src/event_lane_routed_parent/waveform_tt_result.json \
  --consumer-pex /src/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice \
  --work /work/candidates --output /work/result.json
