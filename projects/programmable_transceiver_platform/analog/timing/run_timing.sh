#!/usr/bin/env bash
# Regenerate the timing family: layout (Magic, digital image), DRC, LVS
# (Netgen), extracted ngspice simulations (analog image), corner sweeps and
# generated/<block>-evidence.json.  All containers run with --network none.
# Usage: analog/timing/run_timing.sh [block,block,...]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
BLOCKS="${1:-wordclk,lo_ext,polyphase,pll_ring,prescale,diff_clk_rx,clk_obs,ring_osc,aosc,clockmux,vco_replica}"
docker image inspect svalbard/librelane-gf180-canary:2026.08 >/dev/null
docker image inspect docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 >/dev/null
cd "$HERE"
python3 fastcells.py          # compact fast cells (macros) first
python3 run_timing.py --blocks "$BLOCKS"
python3 evidence.py --blocks "$BLOCKS"
