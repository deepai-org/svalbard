#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label integrated-serializer-tx \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 4 --memory 8g \
  --command /src/serializer/container_integrated_tx.sh \
  --copy integrated-tx-1p25-result.json:integrated-tx-1p25-result.json \
  --copy integrated-tx-2p5-result.json:integrated-tx-2p5-result.json
