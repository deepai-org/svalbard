#!/usr/bin/env bash
set -euo pipefail

python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /src/clock_pulse/clock_pulse_generator.spice \
  --output /work/clock_pulse_generator_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/clock_pulse_generator_layout.tcl > /work/layout.log 2>&1
test -s /work/clock_pulse_generator.gds
printf '{"result":"pass"}\n' > /work/pulse-layout-smoke.json
