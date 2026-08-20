#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label integrated-serializer-tx-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 4 --memory 8g \
  --command /src/serializer/container_integrated_tx_physical.sh \
  --copy integrated-tx-extracted-1p25.json:integrated-tx-extracted-1p25.json \
  --copy integrated-tx-extracted-2p5.json:integrated-tx-extracted-2p5.json \
  --copy integrated-tx-physical-result.json:integrated-tx-physical-result.json \
  --copy integrated-serializer-tx.pex.spice:integrated-serializer-tx.pex.spice \
  --copy layout-integrated-serializer-tx.png:layout-integrated-serializer-tx.png
