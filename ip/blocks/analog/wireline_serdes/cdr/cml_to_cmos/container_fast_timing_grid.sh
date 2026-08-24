#!/usr/bin/env bash
set -euo pipefail

common_args=(
  --source /src
  --pex /src/cml_to_cmos/cml_to_cmos_fast.pex.spice
  --jobs 2 --timeout-s 300
  --boost-policy calibrated --boost-fraction 1.0
  --eval-width-ps 550 --capture-delay-ps 430 --capture-width-ps 100
  --sample-delay-ps 120 --sample-delay-ps 200 --sample-delay-ps 300
  --sample-delay-ps 400 --sample-delay-ps 500 --sample-delay-ps 600
  --sample-delay-ps 700 --sample-delay-ps 750 --sample-delay-ps 760
  --sample-delay-ps 770 --sample-delay-ps 780 --sample-delay-ps 790
  --case typical_3p30_p27_cm0p70_in0p20_load50
  --case ff_2p97_p125_cm0p80_in0p20_load50
  --case ss_2p97_p125_cm0p60_in0p20_load50
)

python3 /src/cml_to_cmos/run_pvt.py "${common_args[@]}" \
  --pipeline-latency-ui 0 --work /work/fast-grid-current \
  --output /work/fast-grid-current.json || true
python3 /src/cml_to_cmos/run_pvt.py "${common_args[@]}" \
  --pipeline-latency-ui 1 --work /work/fast-grid-previous \
  --output /work/fast-grid-previous.json || true

python3 /src/cml_to_cmos/check_fast_timing_grid.py \
  --current /work/fast-grid-current.json \
  --previous /work/fast-grid-previous.json
