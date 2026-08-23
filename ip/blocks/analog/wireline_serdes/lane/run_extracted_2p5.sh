#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-extracted-2p5 --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_extracted_2p5.sh --timeout 35m --cpus 4 --memory 14g \
  --copy extracted-2p5.json:serdes-lane-extracted-2p5-last.json \
  --copy physical-2p5.json:serdes-lane-extracted-2p5-physical-last.json \
  --copy serdes_termination-pex/serdes_termination.pex.spice:serdes-lane-extracted-2p5-termination-last.pex.spice \
  --copy serdes_rx-pex/serdes_rx.pex.spice:serdes-lane-extracted-2p5-rx-last.pex.spice \
  --copy cdr_sampler-pex/cdr_sampler.pex.spice:serdes-lane-extracted-2p5-sampler-last.pex.spice \
  --copy data-restorer-2p5-physical.json:serdes-lane-extracted-2p5-restorer-physical-last.json \
  --copy cml_data_restorer_2p5-pex/cml_data_restorer_2p5.pex.spice:serdes-lane-extracted-2p5-restorer-last.pex.spice \
  --copy data-restorer-2p5-layout.png:serdes-lane-extracted-2p5-restorer-layout-last.png
