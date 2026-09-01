#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-retimed-recovery-schematic \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_retimed_recovery_schematic.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed-recovery-schematic-result.json:pcie-pulse-retimed-recovery-schematic-last.json \
  --copy retimed_recovery_dual_control_pulse.spice:pcie-pulse-retimed-recovery-last.spice
