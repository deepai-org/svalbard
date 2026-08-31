#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_hclk_window_contract.py
python3 /src/clock_pulse_hclk_window_probe/test_sense_write_composition.py
python3 /src/clock_pulse_hclk_window_probe/run_hclk_window_probe.py \
  || test -s /work/hclk-window-result.json
python3 /src/clock_pulse_hclk_window_probe/run_sense_write_composition.py \
  || test -s /work/sense-write-composition-result.json
