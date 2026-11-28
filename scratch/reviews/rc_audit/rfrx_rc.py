#!/usr/bin/env python3
"""rxmix / bbfilter on the published rf_rx benches (tb.py, unchanged) for the C-only and the R+C view.
  python3 rfrx_rc.py rxmix_i <rc.spice>  -> x/<block>/bench.json"""
import sys, json, shutil
from pathlib import Path
R = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx'); sys.path.insert(0, str(R))
import rfrx_flow as flow, tb
blk, rc = sys.argv[1], Path(sys.argv[2]).resolve()
X = Path(__file__).resolve().parent / 'x' / blk
NOM, SS = ('typical', 27, 3.3), ('ss', 32, 3.15)
out = {}
for view, net in (('conly', R / 'generated' / f'{blk}.ext.spice'), ('rc', rc)):
    g = X / f'gen_{view}'; g.mkdir(parents=True, exist_ok=True); shutil.copy(net, g / f'{blk}.ext.spice')
    flow.GENERATED = g; w = X / f'w_{view}'
    if blk.startswith('rxmix'):
        out[view] = dict(nom=tb.rxmix_tran(w, 'ext', NOM, blk), real_tt=tb.rxmix_tran(w, 'ext', NOM, blk, lo=tb.LO_REAL['ext_best_1v16']),
                         real_ss=tb.rxmix_tran(w, 'ext', SS, blk, lo=tb.LO_REAL['cml_1v05']))
    shutil.rmtree(w, ignore_errors=True)
    print(view, json.dumps(out[view], default=str)[:1200], flush=True)
json.dump(out, open(X / 'bench.json', 'w'), indent=1, default=str)
