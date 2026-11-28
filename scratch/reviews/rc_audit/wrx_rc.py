#!/usr/bin/env python3
"""Run the wired_rx family bench (run_family.sim_block, unchanged) on the C-only and on the R+C view of one block.
  python3 wrx_rc.py <block> <rc.spice> [corner temp vdd]  -> x/<block>/bench.json"""
import sys, json, shutil, os
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import wrx_flow as f, run_family as rf
blk, rc = sys.argv[1], Path(sys.argv[2]).resolve()
c, t, v = (sys.argv[3], int(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else ('typical', 27, 3.3)
X = Path(__file__).resolve().parent / 'x' / blk
res = {}
for view, net in (('conly', W / 'generated' / f'{blk}.ext.spice'), ('rc', rc)):
    g = X / f'gen_{view}'; g.mkdir(parents=True, exist_ok=True); shutil.copy(net, g / f'{blk}.ext.spice')
    f.GENERATED = g; f.SCRATCH = X / f'sim_{view}'
    res[view] = rf.sim_block(blk, 'ext', c, t, v)
    shutil.rmtree(f.SCRATCH, ignore_errors=True)
json.dump(dict(block=blk, corner=[c, t, v], rc_netlist=str(rc), results=res), open(X / f'bench_{c}_{t}_{v}.json', 'w'), indent=1, default=str)
for view, r in res.items():
    print(view, json.dumps(r, default=str)[:1500])
