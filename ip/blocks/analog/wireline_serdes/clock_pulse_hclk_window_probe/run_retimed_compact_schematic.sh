#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-retimed-compact-schematic \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_retimed_compact_schematic.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed-compact-result.json:pcie-pulse-retimed-compact-schematic-last.json \
  --copy retimed_compact_recovery.spice:pcie-pulse-retimed-compact-last.spice
