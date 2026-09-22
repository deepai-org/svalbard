#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/test_host_margin.py
python3 -B /src/verification/screen_supply_path.py
tar -czf /work/supply-path-waveforms.tar.gz -C /work typical_25_10_prbs7_drive8_r1_ld2_lc1_sr0.25_sl2_gear20ps typical_25_10_prbs7_drive8_r1_ld2_lc1_sr0.25_sl2_gear10ps
