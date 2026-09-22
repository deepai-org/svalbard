#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/screen_artix_load.py
tar -czf /work/artix-load-waveforms.tar.gz -C /work typical_25_8_alternating typical_25_8_prbs7
