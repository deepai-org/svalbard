#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --revision retimed_joint_long_6_3 \
  --output /work/retimed_recovery_dual_control_pulse.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/retimed_recovery_dual_control_pulse.spice \
  --top recovery_dual_control_pulse \
  --output /work/retimed_recovery_dual_control_pulse_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/retimed_recovery_dual_control_pulse_layout.tcl > /work/retimed-layout.log 2>&1
sak-drc.sh -m -w /work/retimed-drc /work/recovery_dual_control_pulse.mag \
  > /work/retimed-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/retimed-lvs \
  -s /work/retimed_recovery_dual_control_pulse.spice \
  -l /work/recovery_dual_control_pulse.mag \
  -c recovery_dual_control_pulse > /work/retimed-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n recovery_dual_control_pulse_pex \
  -w /work/retimed-pex /work/recovery_dual_control_pulse.mag \
  > /work/retimed-pex-stage.log 2>&1
cp /work/retimed-pex/recovery_dual_control_pulse.pex.spice \
  /work/retimed_recovery_dual_control_pulse.pex.spice
retimed_rc=0
RECOVERY_CONTRACT_PATH=/src/clock_pulse_hclk_window_probe/retimed_recovery_contract.json \
  python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/retimed_recovery_dual_control_pulse.pex.spice \
  --top recovery_dual_control_pulse_pex \
  --netlist-kind full_rc_pex \
  --internal-probes \
  --environment-ids tt ss_hot \
  --work /work/retimed-recovery-pex-cases \
  --output /work/retimed-recovery-physical-probe.json || retimed_rc=$?
# Electrical rejection is evidence. Tool, deck, or incomplete-measure failures
# use a different exit status and remain fatal.
if [[ "$retimed_rc" -ne 0 && "$retimed_rc" -ne 1 ]]; then
  exit "$retimed_rc"
fi
RECOVERY_CONTRACT_PATH=/src/clock_pulse_hclk_window_probe/retimed_recovery_contract.json \
  python3 /src/clock_pulse_hclk_window_probe/localize_recovery_pex.py \
  --pex /work/retimed_recovery_dual_control_pulse.pex.spice \
  --work /work/retimed-recovery-pex-localization \
  --output /work/retimed-recovery-pex-localization.json
