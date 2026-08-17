#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_ac_pvt.py --source /src --work /work/schematic-ac --output /work/schematic-ac.json
python3 /src/run_threshold_pvt.py --source /src --calibration /work/schematic-ac.json \
  --work /work/schematic-threshold --output /work/schematic-threshold.json &
schematic_threshold_pid=$!
python3 /src/run_transient_pvt.py --source /src --calibration /work/schematic-ac.json \
  --work /work/schematic-transient --output /work/schematic-transient.json &
schematic_transient_pid=$!
wait "$schematic_threshold_pid"
wait "$schematic_transient_pid"

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/serdes_rx.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/serdes_rx.spice \
  -l /work/serdes_rx.mag -c serdes_rx > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n serdes_rx_pex -w /work/pex \
  /work/serdes_rx.mag > /work/pex-stage.log 2>&1

pex=/work/pex/serdes_rx.pex.spice
python3 /src/run_ac_pvt.py --source /src --pex "$pex" \
  --work /work/extracted-ac --output /work/extracted-ac.json
python3 /src/run_threshold_pvt.py --source /src --pex "$pex" --calibration /work/extracted-ac.json \
  --work /work/extracted-threshold --output /work/extracted-threshold.json &
extracted_threshold_pid=$!
python3 /src/run_transient_pvt.py --source /src --pex "$pex" --calibration /work/extracted-ac.json \
  --work /work/extracted-transient --output /work/extracted-transient.json &
extracted_transient_pid=$!
wait "$extracted_threshold_pid"
wait "$extracted_transient_pid"
python3 /src/run_noise.py --source /src --pex "$pex" --calibration /work/extracted-ac.json \
  --work /work/noise --output /work/noise.json
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --schematic-ac /work/schematic-ac.json \
  --schematic-threshold /work/schematic-threshold.json \
  --schematic-transient /work/schematic-transient.json \
  --extracted-ac /work/extracted-ac.json --extracted-threshold /work/extracted-threshold.json \
  --extracted-transient /work/extracted-transient.json --noise /work/noise.json \
  --drc /work/drc/serdes_rx.magic.drc/serdes_rx.magic.drc.rpt \
  --lvs /work/lvs/serdes_rx.magic.lvs/serdes_rx.lvs.out \
  --pex "$pex" --render /work/serdes_rx-layout.png --output /work/result.json
