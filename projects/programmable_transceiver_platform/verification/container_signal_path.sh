#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/test_host_margin.py
python3 -B /src/verification/screen_signal_path.py
tar -czf /work/signal-path-waveforms.tar.gz -C /work typical_25_10_prbs7_drive8_r1_ld1_lc1 typical_25_10_prbs7_drive8_r1_ld2_lc1
