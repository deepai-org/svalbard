#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_restorer() {
  local name="$1" phase="$2"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
    --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
    --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
    --mos-corner ss --res-corner res_ss --vdd 2.97 --temperature 125 \
    --tx-bias 1.20 --rx-bias 1.10 \
    --restorer-mode data --restorer-bias 1.30 --sampler-phase "$phase" \
    --work "/work/restorer-${name}" --output "/work/restorer-${name}.json"
}

run_restorer ph045 45.0 & p1=$!
run_restorer ph067 67.5 & p2=$!
run_restorer ph078 78.75 & p3=$!
run_restorer ph090 90.0 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_restorer_sweep.py \
  --claim completed_final_geometry_exact_pex_data_restorer_phase_screen \
  --axis sampler_phase_deg \
  --expected ph045=45.0 --expected ph067=67.5 \
  --expected ph078=78.75 --expected ph090=90.0 \
  --case /work/restorer-ph045.json --case /work/restorer-ph067.json \
  --case /work/restorer-ph078.json --case /work/restorer-ph090.json \
  --output /work/capture-restorer-sweep.json
