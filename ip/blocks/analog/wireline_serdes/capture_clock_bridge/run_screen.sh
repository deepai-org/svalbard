#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-capture-clock-bridge-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/capture_clock_bridge/container_screen.sh \
  --timeout 35m --cpus 2 --memory 6g \
  --copy result.json:capture-clock-bridge-screen-last.json
