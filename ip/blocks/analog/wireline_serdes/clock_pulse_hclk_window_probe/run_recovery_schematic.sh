#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-three-control-recovery \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_recovery_schematic.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy recovery-schematic-result.json:pcie-pulse-recovery-schematic-last.json
