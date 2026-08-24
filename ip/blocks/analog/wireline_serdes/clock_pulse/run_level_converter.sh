#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-level-converter \
  --source-rel ip/blocks/analog/wireline_serdes/clock_pulse \
  --command /src/container_level_converter.sh \
  --timeout 15m --cpus 2 --memory 4g \
  --copy level-converter.json:clock-level-converter-last.json
