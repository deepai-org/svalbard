#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_interpolator/layout.tcl > /work/pi-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_interpolator_pex \
  -w /work/pi-pex /work/phase_interpolator.mag > /work/pi-pex-stage.log 2>&1
python3 /src/lane_rx_pi_capture/run_clock_chain.py \
  --source /src/lane_rx_pi_capture --work /work/clock-chain-ss \
  --pi-pex /work/pi-pex/phase_interpolator.pex.spice \
  --restorer-pex /src/pll/pex/clock_restorer_cascade.pex.spice \
  --sampler-pex /src/lane/sampler_2p5.pex.spice \
  --case-id ss_passive --mos-corner ss --res-corner res_ss \
  --temperature 125 --vdd 2.97 --input-common-mode 1.485 \
  --sampler-bias 1.3 --data-p 2.2 --data-n 1.8 \
  --output /work/clock-chain-ss-result.json
