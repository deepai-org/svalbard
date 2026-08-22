#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-lane-extracted --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/lane/container_extracted.sh --timeout 40m --cpus 4 --memory 10g \
  --copy extracted.json:serdes-lane-extracted-last.json \
  --copy pvt.json:serdes-lane-pvt-last.json \
  --copy physical.json:serdes-lane-physical-last.json
