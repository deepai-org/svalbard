#!/usr/bin/env bash
set -euo pipefail

python3 /src/cml_to_cmos/run_pvt.py \
  --source /src --dut /src/cml_to_cmos/cml_to_cmos_fast.spice \
  --work /work/fast-probe --output /work/fast-probe.json --jobs 2 \
  --waveform-dir /work/waves \
  --boost-policy calibrated --boost-fraction 1.0 \
  --pipeline-latency-ui 1 \
  --eval-width-ps 550 --capture-delay-ps 430 --capture-width-ps 100 \
  --sample-delay-ps 120 \
  --case ss_2p97_p125_cm0p60_in0p20_load50 \
  --case ss_2p97_p125_cm0p80_in0p20_load50 \
  --case ff_2p97_p125_cm0p80_in0p20_load50 \
  --case ff_3p63_m40_cm0p60_in0p20_load50 \
  --case typical_3p30_p27_cm0p70_in0p20_load50 \
  --case ss_3p63_m40_cm0p80_in0p20_load50 \
  --case typical_2p97_m40_cm0p70_in0p20_load50 \
  --case typical_3p63_p125_cm0p70_in0p20_load50 \
  --case ff_3p30_p27_cm0p80_in0p20_load50 \
  --case ss_3p30_p27_cm0p60_in0p20_load50

python3 /src/cml_to_cmos/check_fast_schematic.py \
  --dut /src/cml_to_cmos/cml_to_cmos_fast.spice \
  --result /work/fast-probe.json
