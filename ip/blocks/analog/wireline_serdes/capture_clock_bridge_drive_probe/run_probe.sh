#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-capture-bridge-drive-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/capture_clock_bridge_drive_probe/container_probe.sh \
  --timeout 20m --cpus 4 --memory 8g \
  --copy drive-probe.json:pcie-capture-bridge-drive-probe-last.json
