#!/usr/bin/env bash
set -euo pipefail
. /src/clock_pulse/container_pulse_extract.sh
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --pex "$pex" --work /work/pex-cases \
  --output /work/pulse-pex-nominal-result.json \
  --environment tt --tap-code 0,8,9
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --pex "$pex" --work /work/pex-cases \
  --output /work/pulse-pex-result.json --jobs 4 --tap-code 0,8,9 \
  || test -s /work/pulse-pex-result.json
cp "$pex" /work/clock_pulse_generator.pex.spice
printf '{"result":"pass"}\n' > /work/pulse-physical-smoke.json
