#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label integrated-serializer-tx-2p5-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 20m --cpus 2 --memory 5g \
  --command /src/serializer/container_integrated_tx_2p5_physical.sh \
  --copy integrated-tx-2p5-physical-result.json:integrated-tx-2p5-physical-last.json \
  --copy integrated-serializer-tx-2p5.pex.spice:integrated-serializer-tx-2p5-last.pex.spice \
  --copy layout-integrated-serializer-tx-2p5.png:layout-integrated-serializer-tx-2p5-last.png
