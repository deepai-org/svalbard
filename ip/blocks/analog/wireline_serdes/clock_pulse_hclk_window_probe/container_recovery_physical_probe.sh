#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --output /work/recovery_dual_control_pulse.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/recovery_dual_control_pulse.spice \
  --top recovery_dual_control_pulse \
  --output /work/recovery_dual_control_pulse_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/recovery_dual_control_pulse_layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/recovery_dual_control_pulse.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /work/recovery_dual_control_pulse.spice \
  -l /work/recovery_dual_control_pulse.mag \
  -c recovery_dual_control_pulse > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n recovery_dual_control_pulse_pex \
  -w /work/pex /work/recovery_dual_control_pulse.mag \
  > /work/pex-stage.log 2>&1
cp /work/pex/recovery_dual_control_pulse.pex.spice \
  /work/recovery_dual_control_pulse.pex.spice
python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/recovery_dual_control_pulse.pex.spice \
  --top recovery_dual_control_pulse_pex \
  --netlist-kind full_rc_pex \
  --internal-probes \
  --environment-ids tt ss_hot \
  --work /work/recovery-pex-cases \
  --output /work/recovery-physical-probe.json
