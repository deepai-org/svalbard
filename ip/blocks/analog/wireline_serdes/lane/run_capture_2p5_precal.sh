#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-precal \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_precal.sh \
  --timeout 40m --cpus 4 --memory 14g \
  --copy capture-2p5-precal.json:serdes-lane-capture-2p5-precal-last.json \
  --copy capture-2p5-tt.json:serdes-lane-capture-2p5-precal-tt-last.json \
  --copy capture-2p5-ff_cold.json:serdes-lane-capture-2p5-precal-ff-cold-last.json \
  --copy capture-2p5-ff_hot.json:serdes-lane-capture-2p5-precal-ff-hot-last.json \
  --copy capture-2p5-ss_hot.json:serdes-lane-capture-2p5-precal-ss-hot-last.json \
  --copy capture-2p5-ss_passive.json:serdes-lane-capture-2p5-precal-ss-passive-last.json \
  --copy capture-physical.json:serdes-lane-capture-2p5-precal-physical-last.json \
  --copy cml_to_cmos-pex/cml_to_cmos.pex.spice:serdes-lane-capture-2p5-precal-frontend-last.pex.spice \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-2p5-precal-deserializer-last.pex.spice
