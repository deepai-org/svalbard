#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_local_clock_fanout_source.py
python3 /src/clock_pulse_hclk_window_probe/compile_local_clock_fanout_source.py \
  --output /work/local_clock_fanout.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/local_clock_fanout.spice --top local_clock_fanout \
  --output /work/local_clock_fanout_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/local_clock_fanout_layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/clock_pulse_hclk_window_probe/render_local_clock_fanout.py \
  > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/local_clock_fanout.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /work/local_clock_fanout.spice \
  -l /work/local_clock_fanout.mag -c local_clock_fanout \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n local_clock_fanout_pex \
  -w /work/pex /work/local_clock_fanout.mag > /work/pex-stage.log 2>&1
pex=/work/pex/local_clock_fanout.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
cp "$pex" /work/local_clock_fanout.pex.spice
python3 /src/clock_pulse_hclk_window_probe/summarize_local_clock_fanout_physical.py
