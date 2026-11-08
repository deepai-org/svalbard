#!/usr/bin/env bash
# Regenerate the whole converter family inside the pinned images (--network none).
#   ./run_converters.sh            # macros + all blocks + corner sweeps
#   ./run_converters.sh --quick    # reuse committed macros, nominal sims only
# Raw output: <repo>/scratch/converters/ ; committed outputs: generated/
set -euo pipefail
cd "$(dirname "$0")"
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
# RTL self-checks (host iverilog)
mkdir -p ../../../../scratch/converters
iverilog -g2012 -s tb_adc_sar_logic -o ../../../../scratch/converters/tb_sar.vvp rtl/tb_adc_sar_logic.v rtl/adc_sar_logic.v rtl/adc_sar_delay.v
vvp ../../../../scratch/converters/tb_sar.vvp | grep -E 'PASS|FAIL'
iverilog -g2012 -s tb_dac_logic -o ../../../../scratch/converters/tb_dac.vvp rtl/tb_dac_logic.v rtl/dac_logic.v
vvp ../../../../scratch/converters/tb_dac.vvp | grep -E 'PASS|FAIL'
iverilog -g2012 -s tb_adc_code_reg -o ../../../../scratch/converters/tb_cr.vvp rtl/tb_adc_code_reg.v rtl/adc_code_reg.v
vvp ../../../../scratch/converters/tb_cr.vvp | grep -E 'PASS|FAIL'
if [ $QUICK = 0 ]; then
  python3 flow.py harden adc_code_reg dac_logic   # committed adc_sar_logic macro only feeds circuits.adc() geometry
  python3 flow.py block refbuf --corners all
  python3 flow.py block dac_i adc_i --corners extremes
  python3 flow.py block dac_q adc_q --corners minimal
  python3 adc_fft.py adc_i 32                       # hours: extracted 32-point FFT
else
  python3 flow.py block refbuf dac_i dac_q adc_i adc_q --corners none
fi
