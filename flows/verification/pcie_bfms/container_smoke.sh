#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/work/src/bfm.cocotbext_pcie:/work/src/python.cocotbext_axi:/work/src/python.cocotb_bus/src:/work/src/python.cocotb_test"

cd /work/src/bfm.cocotbext_pcie/tests/pcie
make SIM=icarus COCOTB_LOG_LEVEL=WARNING >/dev/null 2>&1

cd /work/src/bfm.pcievhost/verilog/test
ulimit -f 65536
make -f makefile.verilator run ARCHFLAG= TRACEFLAG= VCDFLAG= > /work/pcievhost.log 2>&1

python3 /runner/check_results.py \
  /work/src/bfm.cocotbext_pcie/tests/pcie/results.xml \
  /work/pcievhost.log \
  /work/source-audit.json \
  /work/result.json
