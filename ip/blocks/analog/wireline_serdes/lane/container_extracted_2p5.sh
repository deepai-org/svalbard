#!/usr/bin/env bash
set -euo pipefail

source /src/lane/capture_stack.sh
prepare_lane_base_stack
prepare_data_restorer_2p5

lane_2p5_args=(
  --source /src --jobs 4
  --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
  --term-pex /src/lane/termination_2p5.pex.spice
  --rx-pex /src/lane/rx_2p5.pex.spice
  --sampler-pex /src/lane/sampler_2p5.pex.spice
  --base-physical /src/lane/physical_2p5_result.json
  --restorer-pex /src/data_restorer/data_restorer_2p5.pex.spice
  --restorer-physical /src/data_restorer/physical_2p5_result.json
  --restorer-cell cml_data_restorer_2p5_pex
)
python3 /src/lane/run_lane.py "${lane_2p5_args[@]}" \
  --serial-rate-gbd 2.5 --tx-bias 1.2 --rx-bias 1.3 --restorer-bias 1.3 \
  --sampler-bias 1.1 --ac-initial-v 0.950 \
  --work /work/extracted-2p5 --output /work/extracted-2p5.json

python3 /src/lane/check_physical.py --serial-rate-gbd 2.5 \
  --termination-drc /work/serdes_termination-drc/serdes_termination.magic.drc/serdes_termination.magic.drc.rpt \
  --termination-lvs /work/serdes_termination-lvs/serdes_termination.magic.lvs/serdes_termination.lvs.out \
  --termination-pex /work/serdes_termination-pex/serdes_termination.pex.spice \
  --termination-simulation-pex /src/lane/termination_2p5.pex.spice \
  --rx-drc /work/serdes_rx-drc/serdes_rx.magic.drc/serdes_rx.magic.drc.rpt \
  --rx-lvs /work/serdes_rx-lvs/serdes_rx.magic.lvs/serdes_rx.lvs.out \
  --rx-pex /work/serdes_rx-pex/serdes_rx.pex.spice \
  --rx-simulation-pex /src/lane/rx_2p5.pex.spice \
  --sampler-drc /work/cdr_sampler-drc/cdr_sampler.magic.drc/cdr_sampler.magic.drc.rpt \
  --sampler-lvs /work/cdr_sampler-lvs/cdr_sampler.magic.lvs/cdr_sampler.lvs.out \
  --sampler-pex /work/cdr_sampler-pex/cdr_sampler.pex.spice \
  --sampler-simulation-pex /src/lane/sampler_2p5.pex.spice \
  --release-physical /src/lane/physical_2p5_result.json \
  --lane /work/extracted-2p5.json --output /work/physical-2p5.json
