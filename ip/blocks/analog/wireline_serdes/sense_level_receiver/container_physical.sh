#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/compile_variant.py --variant sense \
  --top sense_level_receiver --spice-output /work/sense_level_receiver.spice \
  --layout-output /work/sense_level_receiver_layout.tcl \
  --manifest-output /work/variant_manifest.json
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/sense_level_receiver_layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/sense_level_receiver.mag > /work/drc.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /work/sense_level_receiver.spice \
  -l /work/sense_level_receiver.mag -c sense_level_receiver > /work/lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n sense_level_receiver_pex \
  -w /work/pex /work/sense_level_receiver.mag > /work/pex.log 2>&1
pex=/work/pex/sense_level_receiver.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp /work/sense_level_receiver.gds /work/reference_level_receiver.gds
python3 /src/reference_level_receiver/render_layout.py > /work/render.log 2>&1
python3 /src/reference_level_receiver/check_physical.py \
  --drc /work/drc/sense_level_receiver.magic.drc/sense_level_receiver.magic.drc.rpt \
  --lvs /work/lvs/sense_level_receiver.magic.lvs/sense_level_receiver.lvs.out \
  --pex "$pex" --gds /work/sense_level_receiver.gds \
  --render /work/reference-level-receiver-layout.png \
  --layout /work/sense_level_receiver_layout.tcl \
  --schematic /work/sense_level_receiver.spice --output /work/physical.json
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut "$pex" --dut-subckt sense_level_receiver_pex \
  --work /work/leaf-cases --output /work/leaf-result.json
python3 /src/reference_level_receiver/select_single_output_controls.py \
  --evidence /work/leaf-result.json --output /work/control-plan.json
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut "$pex" --dut-subckt sense_level_receiver_pex \
  --consumer-pex /src/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice \
  --control-plan /work/control-plan.json \
  --work /work/consumer-cases --output /work/consumer-result.json
cp "$pex" /work/sense_level_receiver.pex.spice
