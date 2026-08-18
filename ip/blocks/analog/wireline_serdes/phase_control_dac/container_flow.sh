#!/usr/bin/env bash
set -euo pipefail
python3 /src/run_dc.py --source /src --work /work/schematic-dc --output /work/schematic-dc.json --jobs 4
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/layout.tcl >/work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/phase_control_dac.mag >/work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/phase_control_dac.spice -l /work/phase_control_dac.mag -c phase_control_dac >/work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_control_dac_pex -w /work/pex /work/phase_control_dac.mag >/work/pex-stage.log 2>&1
pex=/work/pex/phase_control_dac.pex.spice
python3 /src/run_dc.py --source /src --pex "$pex" --work /work/extracted-dc --output /work/extracted-dc.json --jobs 4
python3 /src/run_settling.py --source /src --pex "$pex" --work /work/settling --output /work/settling.json --jobs 4
klayout -b -r /src/render_layout.py >/work/render.log 2>&1
python3 /src/check_results.py --schematic /work/schematic-dc.json --extracted /work/extracted-dc.json --settling /work/settling.json \
 --drc /work/drc/phase_control_dac.magic.drc/phase_control_dac.magic.drc.rpt --lvs /work/lvs/phase_control_dac.magic.lvs/phase_control_dac.lvs.out \
 --pex "$pex" --gds /work/phase_control_dac.gds --render /work/phase_control_dac-layout.png --output /work/result.json
