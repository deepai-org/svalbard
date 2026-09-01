#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-retimed-latched-schematic \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_retimed_latched_schematic.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed-latched-result.json:pcie-pulse-retimed-latched-schematic-last.json \
  --copy retimed_latched_recovery.spice:pcie-pulse-retimed-latched-last.spice
