#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-stress-pvt --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_stress_pvt.sh --timeout 35m --cpus 4 --memory 14g \
  --copy capture-stress-pvt.json:serdes-lane-capture-stress-pvt-last.json \
  --copy capture-physical.json:serdes-lane-capture-stress-pvt-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-stress-pvt-deserializer-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-stress-pvt-layout-last.png \
  --copy data-restorer-physical.json:serdes-lane-capture-stress-pvt-restorer-physical-last.json \
  --copy cml_data_restorer-pex/cml_data_restorer.pex.spice:serdes-lane-capture-stress-pvt-restorer-last.pex.spice \
  --copy data-restorer-layout.png:serdes-lane-capture-stress-pvt-restorer-layout-last.png
