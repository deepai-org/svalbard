#!/usr/bin/env bash
set -euo pipefail

python3 /src/lane/run_capture_stress_case.py \
  --source /src --work /work/ss-regenerative-aperture \
  --output /work/ss-regenerative-aperture.json --jobs 2 \
  --serial-rate-gbd 2.5 \
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice \
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json \
  --rx-regenerative-capture-parent-pex \
    /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --rx-regenerative-capture-parent-physical \
    /src/lane_rx_regenerative_capture/physical_result.json \
  --pattern prbs7 --bit-count 16 --simulation-timeout-s 900 \
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
  --restorer-mode none --capture-width-ps 150 --capture-delay-ps 200 \
  --capture-output-delay-ps 1050 --frontend-sense-width-ps 550 \
  --frontend-tail-boost --mos-corner ss --res-corner res_ff \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 \
  --latency-ui 0 --sampler-latency-ui 0 --frontend-latency-ui 2 \
  --frontend-write-latency-ui 2 --capture-latency-ui 2 \
  --offset-ps 0 --offset-ps 50 --offset-ps 100 --offset-ps 150 --offset-ps 200 \
  --case-id ss_hot_regenerative_aperture
