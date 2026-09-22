#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/screen_drive_strength.py
tar -czf /work/drive-strength-waveforms.tar.gz -C /work typical_25_8_alternating_drive12 typical_25_8_prbs7_drive12 typical_25_8_alternating_drive16 typical_25_8_prbs7_drive16
