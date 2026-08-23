#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-capture-2p5-fast-cal \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_capture_2p5_fast_cal.sh \
  --timeout 35m --cpus 2 --memory 9g \
  --copy capture-2p5-ff_cold.json:serdes-lane-capture-2p5-fast-ff-cold-last.json \
  --copy capture-2p5-ff_hot.json:serdes-lane-capture-2p5-fast-ff-hot-last.json \
  --copy capture-physical.json:serdes-lane-capture-2p5-fast-physical-last.json \
  --copy deserializer_split_capture-pex/deserializer_split_capture.pex.spice:serdes-lane-capture-2p5-fast-deserializer-last.pex.spice \
  --copy cml_to_cmos-pex/cml_to_cmos.pex.spice:serdes-lane-capture-2p5-fast-frontend-last.pex.spice \
  --copy capture-layout.png:serdes-lane-capture-2p5-fast-layout-last.png
