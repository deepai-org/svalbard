#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" --label serdes-capture-clock-bridge-physical --source-rel ip/blocks/analog/wireline_serdes --command /src/capture_clock_bridge/container_physical.sh --timeout 40m --cpus 2 --memory 8g --copy physical.json:capture-clock-bridge-physical-last.json --copy screen.json:capture-clock-bridge-pex-screen-last.json --copy capture_clock_bridge.pex.spice:capture-clock-bridge-last.pex.spice --copy capture-clock-bridge-layout.png:capture-clock-bridge-layout-last.png
