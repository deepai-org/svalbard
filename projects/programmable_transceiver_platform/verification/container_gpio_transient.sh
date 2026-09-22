#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_gpio_transient.py
python3 -B /src/verification/run_gpio_transient.py --work /work --output /work/gpio-transient.json
