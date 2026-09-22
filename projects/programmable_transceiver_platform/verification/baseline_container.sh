#!/bin/sh
set -eu
PYTHONDONTWRITEBYTECODE=1 python3 /src/verification/generate_crc.py --check
yosys -Q -T -p 'read_verilog -sv -I/src/rtl /src/sim/crc_equivalence.sv; prep -top crc_equivalence; sat -verify -prove equal 1 -show-inputs' > /out/crc-equivalence.log
for v in 0 1; do
for m in 0 1; do
  iverilog -g2012 -I/src/rtl -s tb_core -Ptb_core.MODE=$m -Ptb_core.V2=$v -o /out/core$m /src/rtl/*.sv /src/sim/tb_core.sv
  vvp /out/core$m
done
done
for test in control helpers memory release; do
  iverilog -g2012 -I/src/rtl -s tb_$test -o /out/$test /src/rtl/*.sv /src/sim/tb_$test.sv
  vvp /out/$test
done
iverilog -g2012 -s pt_converter_model -o /out/afe /src/sim/pt_afe_model.sv
PYTHONDONTWRITEBYTECODE=1 python3 /src/verification/check_rtl_frames.py
PYTHONDONTWRITEBYTECODE=1 python3 /src/verification/check_rtl_frames.py --v2
yosys -Q -T -p 'read_verilog -sv -I/src/rtl /src/rtl/*.sv; hierarchy -check -top pt_digital; proc; check -assert; stat' > /out/synthesis-structure.log
yosys -Q -T -p 'read_verilog -sv -I/src/rtl /src/rtl/*.sv /src/integration/pt_chip.sv; hierarchy -check -top pt_chip; proc; check -assert; stat' > /out/chip-structure.log
printf '%s\n' 'BASELINE_PASS (structural synthesis only; no timing or analog signoff)'
