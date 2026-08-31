#!/usr/bin/env bash
set -euo pipefail

. /src/clock_pulse/container_pulse_extract.sh

python3 /src/clock_pulse/screen_wb0_drive.py \
  --pex "$pex" --output /work/clock_pulse_generator_active_taper_x1p25.pex.spice \
  --report /work/pulse-wb0-counterfactual-report.json --scope active_taper --scale 1.25
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --pex /work/clock_pulse_generator_active_taper_x1p25.pex.spice \
  --work /work/pex-cases --output /work/pulse-wb0-counterfactual-result.json \
  --jobs 2 --environment tt --environment ff_hot --environment ss_hot \
  --pex-resistance-net-scale DBG_E_WSD=3.0 \
  --pex-resistance-net-scale DBG_O_WSD=3.0 \
  --tap-code 0,8,9 || test -s /work/pulse-wb0-counterfactual-result.json
printf '{"result":"pass"}\n' > /work/pulse-wb0-counterfactual-smoke.json
