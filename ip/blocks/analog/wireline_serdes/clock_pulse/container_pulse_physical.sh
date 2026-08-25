#!/usr/bin/env bash
set -euo pipefail

python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /src/clock_pulse/clock_pulse_generator.spice \
  --output /work/clock_pulse_generator_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/clock_pulse_generator_layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/clock_pulse/render_pulse_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/clock_pulse_generator.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /src/clock_pulse/clock_pulse_generator.spice \
  -l /work/clock_pulse_generator.mag -c clock_pulse_generator \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n clock_pulse_generator_pex \
  -w /work/pex /work/clock_pulse_generator.mag > /work/pex-stage.log 2>&1
pex=/work/pex/clock_pulse_generator.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --pex "$pex" --work /work/pex-cases \
  --output /work/pulse-pex-nominal-result.json \
  --environment tt --tap-code 0,8,9
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --pex "$pex" --work /work/pex-cases \
  --output /work/pulse-pex-result.json \
  --tap-code 0,10,11 --tap-code 1,8,9 \
  --tap-code 0,8,9 --tap-code 2,8,9
cp "$pex" /work/clock_pulse_generator.pex.spice
printf '{"result":"pass"}\n' > /work/pulse-physical-smoke.json
