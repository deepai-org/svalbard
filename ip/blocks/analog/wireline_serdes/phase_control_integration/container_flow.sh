#!/usr/bin/env bash
set -euo pipefail
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/phase_control_dac/layout.tcl >/work/dac-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_control_dac_pex -w /work/dac-pex /work/phase_control_dac.mag >/work/dac-pex.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/phase_interpolator/layout.tcl >/work/pi-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_interpolator_pex -w /work/pi-pex /work/phase_interpolator.mag >/work/pi-pex.log 2>&1
python3 /src/phase_control_integration/run_composed.py --source /src \
 --dac-pex /work/dac-pex/phase_control_dac.pex.spice --pi-pex /work/pi-pex/phase_interpolator.pex.spice \
 --work /work/composed --output /work/composed.json --jobs 4
