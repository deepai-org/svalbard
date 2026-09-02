#!/usr/bin/env bash
set -euo pipefail
cd /work

for kind in sampler capture; do
  if [[ "$kind" == sampler ]]; then
    top=distributed_sampler_pair
  else
    top=distributed_capture_pair
  fi
  python3 /src/distributed_clock_fanout/compile_branch.py \
    --kind "$kind" --output "/work/$kind.spice"
  python3 /src/distributed_clock_fanout/compile_branch.py \
    --kind "$kind" --flatten-for-lvs --output "/work/$kind-lvs.spice"
  python3 /src/clock_pulse/generate_pulse_layout.py \
    --source "/work/$kind.spice" --top "$top" \
    --output "/work/$kind-layout.tcl"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "/work/$kind-layout.tcl" > "/work/$kind-layout.log" 2>&1
  sak-drc.sh -m -w "/work/$kind-drc" "/work/$top.mag" \
    > "/work/$kind-drc.log" 2>&1
  sak-lvs.sh -m -w "/work/$kind-lvs" -s "/work/$kind-lvs.spice" \
    -l "/work/$top.mag" -c "$top" > "/work/$kind-lvs.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${top}_pex" \
    -w "/work/$kind-pex" "/work/$top.mag" > "/work/$kind-pex.log" 2>&1
  pex="/work/$kind-pex/$top.pex.spice"
  sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
  cp "$pex" "/work/$kind.pex.spice"
done

python3 /src/distributed_clock_fanout/summarize_physical.py \
  --output /work/physical_result.json
