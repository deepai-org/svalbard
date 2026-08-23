#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-data-restorer-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/data_restorer/container_physical.sh \
  --timeout 25m --cpus 2 --memory 4g \
  --copy data-restorer-physical-result.json:serdes-data-restorer-physical-last.json \
  --copy data-restorer.pex.spice:serdes-data-restorer-last.pex.spice \
  --copy layout-data-restorer.png:serdes-data-restorer-layout-last.png
