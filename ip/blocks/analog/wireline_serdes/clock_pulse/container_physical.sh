#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/clock_pulse/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/clock_level_converter.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /src/clock_pulse/clock_level_converter.spice \
  -l /work/clock_level_converter.mag -c clock_level_converter \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n clock_level_converter_pex \
  -w /work/pex /work/clock_level_converter.mag > /work/pex-stage.log 2>&1

pex=/work/pex/clock_level_converter.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
python3 /src/clock_pulse/run_level_converter.py \
  --source /src/clock_pulse --pex "$pex" --work /work/extracted-cases \
  --output /work/extracted-result.json
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_interpolator/layout.tcl > /work/pi-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_interpolator_pex \
  -w /work/pi-pex /work/phase_interpolator.mag > /work/pi-pex-stage.log 2>&1
python3 /src/clock_pulse/run_composed_clock.py \
  --source /src/clock_pulse --work /work/composed-cases \
  --pi-pex /work/pi-pex/phase_interpolator.pex.spice \
  --restorer-pex /src/pll/pex/clock_restorer_cascade.pex.spice \
  --converter-pex "$pex" --output /work/composed-result.json
python3 /src/clock_pulse/render_layout.py > /work/render.log 2>&1
python3 /src/clock_pulse/check_physical.py \
  --source /src/clock_pulse \
  --drc /work/drc/clock_level_converter.magic.drc/clock_level_converter.magic.drc.rpt \
  --lvs /work/lvs/clock_level_converter.magic.lvs/clock_level_converter.lvs.out \
  --pex "$pex" --gds /work/clock_level_converter.gds \
  --render /work/clock_level_converter-layout.png \
  --timing /work/extracted-result.json \
  --composed /work/composed-result.json \
  --output /work/physical-result.json
cp "$pex" /work/clock_level_converter.pex.spice
