#!/usr/bin/env bash
set -euo pipefail
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/capture_clock_bridge/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/capture_clock_bridge.mag > /work/drc.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/capture_clock_bridge/capture_clock_bridge.spice -l /work/capture_clock_bridge.mag -c capture_clock_bridge > /work/lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n capture_clock_bridge_pex -w /work/pex /work/capture_clock_bridge.mag > /work/pex.log 2>&1
pex=/work/pex/capture_clock_bridge.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
klayout -b -r /src/capture_clock_bridge/render_layout.py > /work/render.log 2>&1
python3 /src/capture_clock_bridge/check_physical.py --drc /work/drc/capture_clock_bridge.magic.drc/capture_clock_bridge.magic.drc.rpt --lvs /work/lvs/capture_clock_bridge.magic.lvs/capture_clock_bridge.lvs.out --pex "$pex" --gds /work/capture_clock_bridge.gds --render /work/capture-clock-bridge-layout.png --layout /src/capture_clock_bridge/layout.tcl --schematic /src/capture_clock_bridge/capture_clock_bridge.spice --output /work/physical.json
python3 /src/capture_clock_bridge/run_bridge_screen.py --source /src --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice --capture-physical /src/lane/capture_2p5_fast_physical_result.json --bridge-pex "$pex" --bridge-physical /work/physical.json --work /work/screen --output /work/screen.json
cp "$pex" /work/capture_clock_bridge.pex.spice
