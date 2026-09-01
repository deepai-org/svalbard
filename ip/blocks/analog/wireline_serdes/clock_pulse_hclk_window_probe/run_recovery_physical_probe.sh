#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-three-control-physical-probe \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_recovery_physical_probe.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy recovery-physical-probe.json:pcie-pulse-recovery-physical-probe-last.json \
  --copy recovery-pex-localization.json:pcie-pulse-recovery-pex-localization-last.json \
  --copy recovery_dual_control_pulse.pex.spice:pcie-pulse-recovery-last.pex.spice
