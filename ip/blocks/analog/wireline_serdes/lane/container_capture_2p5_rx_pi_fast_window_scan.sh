#!/usr/bin/env bash
set -euo pipefail

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json
  --rx-pi-capture-parent-pex
    /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.pex.spice
  --rx-pi-capture-parent-physical
    /src/lane_rx_pi_capture/fast_physical_result.json
  --pattern prbs7 --bit-count 16 --simulation-timeout-s 900
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode data --capture-output-delay-ps 1050
  --frontend-sense-width-ps 550 --even-frontend-skew-ps 250
  --pi-control-a 1.15 --pi-control-b 1.15 --pi-buffer-bias 1.15
  --clock-restorer-bias 1.3 --pi-invert --allow-fail
  --mos-corner ss --res-corner res_ss --vdd 2.97 --temperature 125
  --tx-load-code 4 --tx-bias 1.7 --ac-initial-v 1.100
  --rx-bias 1.5 --restorer-bias 1.5 --sampler-bias 1.2
  --sampler-phase 135 --pi-input-phase-deg 135 --rx-window-start-ps 250
  --latency-ui 1 --sampler-latency-ui 1 --frontend-latency-ui 1
  --frontend-write-latency-ui 1 --capture-latency-ui 1 --offset-ps 600
)

points=(400:380 450:320 450:350 500:270 500:300 550:220)
pids=()
cases=()
for point in "${points[@]}"; do
  delay="${point%%:*}"
  width="${point##*:}"
  tag="d${delay}_w${width}"
  output="/work/ss-window-${tag}.json"
  cases+=("$output")
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "ss_window_${tag}" --capture-delay-ps "$delay" \
    --capture-width-ps "$width" --work "/work/ss-window-${tag}" \
    --output "$output" &
  pids+=("$!")
  if ((${#pids[@]} == 2)); then
    wait "${pids[@]}"
    pids=()
  fi
done
if ((${#pids[@]})); then
  wait "${pids[@]}"
fi

merge_args=()
for path in "${cases[@]}"; do
  merge_args+=(--case "$path")
done
python3 /src/lane/summarize_capture_scan.py "${merge_args[@]}" \
  --output /work/ss-window-scan.json
