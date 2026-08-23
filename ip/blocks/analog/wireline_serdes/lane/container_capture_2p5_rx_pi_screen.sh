#!/usr/bin/env bash
set -euo pipefail

python3 /src/lane/run_capture_stress_case.py \
  --source /src --work /work/rx-pi-screen --output /work/rx-pi-screen.json \
  --jobs 2 --serial-rate-gbd 2.5 \
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice \
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json \
  --rx-pi-capture-parent-pex /src/lane_rx_pi_capture/lane_rx_pi_capture.pex.spice \
  --rx-pi-capture-parent-physical /src/lane_rx_pi_capture/physical_result.json \
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900 \
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
  --restorer-mode data --capture-delay-ps 550 --capture-width-ps 380 \
  --capture-output-delay-ps 1050 \
  --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435 \
  --rx-bias 1.3 --restorer-bias 1.3 --sampler-bias 1.3 \
  --sampler-phase 22.5 --latency-ui 0 --rx-window-start-ps 100 \
  --pi-control-a 1.15 --pi-control-b 1.15 --pi-buffer-bias 1.15 \
  --clock-restorer-bias 1.15 \
  --pi-invert \
  --offset-ps 0 --offset-ps 100 --offset-ps 200 --offset-ps 300 \
  --offset-ps 400 --offset-ps 500 --offset-ps 600 --offset-ps 700 \
  --allow-fail --case-id tt_pi_screen
