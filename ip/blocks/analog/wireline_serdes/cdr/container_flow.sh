#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_sampler_pvt.py --source /src --work /work/schematic-pvt \
  --output /work/schematic-pvt.json --jobs 2

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/cdr_sampler.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/cdr_sampler.spice \
  -l /work/cdr_sampler.mag -c cdr_sampler > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cdr_sampler_pex -w /work/pex \
  /work/cdr_sampler.mag > /work/pex-stage.log 2>&1

pex=/work/pex/cdr_sampler.pex.spice
python3 /src/run_sampler_nominal.py --source /src --pex "$pex" \
  --work /work/extracted-nominal --output /work/extracted-nominal.json
python3 /src/run_sampler_pvt.py --source /src --pex "$pex" --work /work/extracted-pvt \
  --output /work/extracted-pvt.json --jobs 2
python3 /src/run_sampler_robustness.py --source /src --pex "$pex" \
  --work /work/robustness --output /work/robustness.json --jobs 2
python3 /src/run_sampler_aperture.py --source /src --pex "$pex" \
  --pvt /work/extracted-pvt.json --work /work/aperture --output /work/aperture.json --jobs 2
python3 /src/run_sampler_supply_noise.py --source /src --pex "$pex" \
  --pvt /work/extracted-pvt.json --work /work/supply-noise \
  --output /work/supply-noise.json --jobs 2
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --schematic-pvt /work/schematic-pvt.json \
  --extracted-nominal /work/extracted-nominal.json \
  --extracted-pvt /work/extracted-pvt.json --robustness /work/robustness.json \
  --aperture /work/aperture.json --supply-noise /work/supply-noise.json \
  --drc /work/drc/cdr_sampler.magic.drc/cdr_sampler.magic.drc.rpt \
  --lvs /work/lvs/cdr_sampler.magic.lvs/cdr_sampler.lvs.out \
  --pex "$pex" --render /work/cdr_sampler-layout.png --output /work/result.json
