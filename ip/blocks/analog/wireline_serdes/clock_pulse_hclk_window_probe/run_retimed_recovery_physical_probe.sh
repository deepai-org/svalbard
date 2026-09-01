#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-pulse-retimed-recovery-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/clock_pulse_hclk_window_probe/container_retimed_recovery_physical_probe.sh \
  --timeout 30m --cpus 8 --memory 12g \
  --copy retimed-recovery-physical-probe.json:pcie-pulse-retimed-recovery-physical-last.json \
  --copy retimed-recovery-pex-localization.json:pcie-pulse-retimed-recovery-pex-localization-last.json \
  --copy retimed_recovery_dual_control_pulse.pex.spice:pcie-pulse-retimed-recovery-last.pex.spice \
  --copy retimed_recovery_dual_control_pulse.spice:pcie-pulse-retimed-recovery-last.spice
