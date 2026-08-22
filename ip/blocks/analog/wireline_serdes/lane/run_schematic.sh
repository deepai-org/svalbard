#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-schematic --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_schematic.sh --timeout 10m --cpus 4 --memory 6g \
  --copy result.json:serdes-lane-schematic-last.json
