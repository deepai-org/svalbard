#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/test_host_margin.py
python3 -B /src/verification/screen_weak_drive.py
tar -czf /work/weak-drive-waveforms.tar.gz -C /work typical_25_8_alternating_drive8 typical_25_8_prbs7_drive8 typical_25_10_alternating_drive8 typical_25_10_prbs7_drive8
