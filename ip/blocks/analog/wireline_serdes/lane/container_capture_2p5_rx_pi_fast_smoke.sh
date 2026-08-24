#!/usr/bin/env bash
set -euo pipefail

python3 /src/lane/run_capture_stress_case.py \
  --source /src --jobs 1 --serial-rate-gbd 2.5 \
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice \
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json \
  --rx-pi-capture-parent-pex \
    /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.pex.spice \
  --rx-pi-capture-parent-physical \
    /src/lane_rx_pi_capture/fast_physical_result.json \
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900 \
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
  --restorer-mode data --capture-width-ps 380 \
  --pi-control-a 1.15 --pi-control-b 1.15 --pi-buffer-bias 1.15 \
  --clock-restorer-bias 1.15 --pi-invert \
  --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435 \
  --rx-bias 1.3 --restorer-bias 1.3 --sampler-bias 1.3 \
  --sampler-phase 22.5 --latency-ui 0 --rx-window-start-ps 100 \
  --frontend-latency-ui 2 --frontend-write-latency-ui 0 \
  --capture-latency-ui 0 \
  --frontend-sense-width-ps 550 --capture-delay-ps 550 \
  --capture-output-delay-ps 1050 --offset-ps 300 \
  --case-id fast_tt \
  --work /work/capture-2p5-rx-pi-fast-tt \
  --output /work/capture-2p5-rx-pi-fast-tt.json
