#!/usr/bin/env bash
set -euo pipefail

common=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json
  --pattern prbs7 --bit-count 12 --simulation-timeout-s 600
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode data --capture-width-ps 380 --capture-output-delay-ps 750
  --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435
  --rx-bias 1.3 --restorer-bias 1.3 --sampler-bias 1.1
  --sampler-phase 22.5 --latency-ui 0 --rx-window-start-ps 100
  --offset-ps 100 --allow-fail
)

python3 /src/lane/run_capture_stress_case.py "${common[@]}" \
  --rx-capture-parent-pex /src/lane_rx_capture/lane_rx_capture.pex.spice \
  --rx-capture-parent-physical /src/lane_rx_capture/physical_result.json \
  --case-id ideal_clock --work /work/ideal --output /work/ideal.json & p1=$!
python3 /src/lane/run_capture_stress_case.py "${common[@]}" \
  --rx-pi-capture-parent-pex /src/lane_rx_pi_capture/lane_rx_pi_capture.pex.spice \
  --rx-pi-capture-parent-physical /src/lane_rx_pi_capture/physical_result.json \
  --pi-control-a 1.15 --pi-control-b 1.15 --pi-buffer-bias 1.15 \
  --clock-restorer-bias 1.0 --pi-invert \
  --case-id pi_clock --work /work/pi --output /work/pi.json & p2=$!
wait "$p1" "$p2"
cp /work/ideal/convert_100p.log /work/ideal-clock.log
cp /work/pi/convert_100p.log /work/pi-clock.log
