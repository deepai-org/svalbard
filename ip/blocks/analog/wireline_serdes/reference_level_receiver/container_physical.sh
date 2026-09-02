#!/usr/bin/env bash
set -euo pipefail
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/reference_level_receiver/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/reference_level_receiver.mag > /work/drc.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/reference_level_receiver/reference_level_receiver.spice -l /work/reference_level_receiver.mag -c reference_level_receiver > /work/lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n reference_level_receiver_pex -w /work/pex /work/reference_level_receiver.mag > /work/pex.log 2>&1
pex=/work/pex/reference_level_receiver.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
klayout -b -r /src/reference_level_receiver/render_layout.py > /work/render.log 2>&1
python3 /src/reference_level_receiver/check_physical.py --drc /work/drc/reference_level_receiver.magic.drc/reference_level_receiver.magic.drc.rpt --lvs /work/lvs/reference_level_receiver.magic.lvs/reference_level_receiver.lvs.out --pex "$pex" --gds /work/reference_level_receiver.gds --render /work/reference-level-receiver-layout.png --layout /src/reference_level_receiver/layout.tcl --schematic /src/reference_level_receiver/reference_level_receiver.spice --output /work/physical.json
python3 /src/reference_level_receiver/run_bias_sweep.py --source /src/clock_pulse --pex "$pex" --dut-subckt reference_level_receiver_pex --work /work/cases --output /work/extracted.json --biases 0.85 0.90 1.00 1.08 1.20 1.40
cp "$pex" /work/reference_level_receiver.pex.spice
