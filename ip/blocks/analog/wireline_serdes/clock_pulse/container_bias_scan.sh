#!/usr/bin/env bash
set -euo pipefail
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/clock_pulse/layout.tcl > /work/layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n clock_level_converter_pex \
  -w /work/pex /work/clock_level_converter.mag > /work/pex-stage.log 2>&1
pex=/work/pex/clock_level_converter.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
python3 /src/clock_pulse/run_bias_scan.py --source /src/clock_pulse \
  --pex "$pex" --work /work/bias-scan --output /work/bias-scan.json
