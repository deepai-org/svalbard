#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label serdes-clock-level-converter-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse/container_physical.sh \
  --timeout 45m --cpus 2 --memory 8g \
  --copy physical-result.json:clock-level-converter-physical-last.json \
  --copy extracted-result.json:clock-level-converter-extracted-last.json \
  --copy composed-result.json:clock-level-converter-composed-last.json \
  --copy clock_level_converter.pex.spice:clock-level-converter-last.pex.spice \
  --copy clock_level_converter-layout.png:clock-level-converter-layout-last.png
