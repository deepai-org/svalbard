#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-calibrated \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_calibrated.sh \
  --timeout 60m --cpus 4 --memory 16g \
  --copy capture-2p5-calibrated.json:serdes-lane-capture-2p5-calibrated-last.json \
  --copy capture-2p5-tt.json:serdes-lane-capture-2p5-calibrated-tt-last.json \
  --copy capture-2p5-ff_cold.json:serdes-lane-capture-2p5-calibrated-ff-cold-last.json \
  --copy capture-2p5-ff_hot.json:serdes-lane-capture-2p5-calibrated-ff-hot-last.json \
  --copy capture-2p5-ss_hot.json:serdes-lane-capture-2p5-calibrated-ss-hot-last.json \
  --copy capture-2p5-ss_passive.json:serdes-lane-capture-2p5-calibrated-ss-passive-last.json \
  --copy integrated-tx-2p5-physical-result.json:serdes-lane-capture-2p5-calibrated-tx-physical-last.json \
  --copy integrated-serializer-tx-2p5.pex.spice:serdes-lane-capture-2p5-calibrated-tx-last.pex.spice \
  --copy layout-integrated-serializer-tx-2p5.png:serdes-lane-capture-2p5-calibrated-tx-layout-last.png \
  --copy capture-physical.json:serdes-lane-capture-2p5-calibrated-physical-last.json \
  --copy cml-to-cmos-physical.json:serdes-lane-capture-2p5-calibrated-frontend-physical-last.json \
  --copy cml_to_cmos-layout.png:serdes-lane-capture-2p5-calibrated-frontend-layout-last.png \
  --copy data-restorer-2p5-calibrated-physical.json:serdes-lane-capture-2p5-calibrated-restorer-physical-last.json \
  --copy cml_data_restorer_2p5_calibrated-pex/cml_data_restorer_2p5_calibrated.pex.spice:serdes-lane-capture-2p5-calibrated-restorer-last.pex.spice \
  --copy data-restorer-2p5-calibrated-layout.png:serdes-lane-capture-2p5-calibrated-restorer-layout-last.png \
  --copy cml_to_cmos-pex/cml_to_cmos.pex.spice:serdes-lane-capture-2p5-calibrated-frontend-last.pex.spice \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-2p5-calibrated-deserializer-last.pex.spice
