#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-hclk-write-window-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_hclk_window_probe.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy hclk-window-result.json:pcie-hclk-write-window-last.json
