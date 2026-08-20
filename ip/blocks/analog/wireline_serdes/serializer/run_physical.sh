#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label serializer-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 4 --memory 8g \
  --command /src/serializer/container_physical.sh \
  --copy serializer-extracted-result.json:serializer-extracted-result.json \
  --copy serializer-2p5g-result.json:serializer-2p5g-result.json \
  --copy serializer-physical-result.json:serializer-physical-result.json \
  --copy serializer.pex.spice:serializer.pex.spice \
  --copy layout-serializer.png:layout-serializer.png
