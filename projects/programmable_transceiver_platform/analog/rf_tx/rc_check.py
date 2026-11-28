#!/usr/bin/env python3
"""rf_tx block R+C check (RFT-07 scope, 2026-11-28): the run_benches mixer / summer benches on the C-only published
netlists and on Magic full-coverage extresist + fixcap16 R+C netlists (generated/cand/<block>.rc.spice).
    python3 rc_check.py      -> generated/rf_tx-rc-check.json"""
import json, os
from pathlib import Path
import simulate as S
import run_benches as B
HERE = Path(__file__).resolve().parent
VIEWS = {'c_only': {}, 'rc': {b: f'generated/cand/{b}.rc.spice' for b in ('txmix_i', 'txmix_q', 'txsum')}}
res = {}
for v, alt in VIEWS.items():
    os.environ['RFTX_VIEWFILES'] = json.dumps(alt)
    decks, meta = {}, {}
    for blk in ('txmix_i', 'txmix_q'):
        for vin in (0.1, 0.3):
            n = f'{blk}_v{int(vin * 1000)}'
            decks[n] = B.mixer_deck('ext', vin=vin, out=f'{n}.txt').replace('pt_txmix_i', f'pt_{blk}'); meta[n] = ('mix', vin)
    decks['sum_on'] = B.sum_deck('ext', out='sum_on.txt'); meta['sum_on'] = ('sum', None)
    work = S.run_decks(decks, f'rccheck_{v}')
    res[v] = {n: (B.mixer_metrics(work, n, a) if k == 'mix' else B.sum_metrics(work, n) if hasattr(B, 'sum_metrics') else None) for n, (k, a) in meta.items()}
    print(v, json.dumps(res[v])[:1500])
json.dump(res, open(HERE / 'generated/rf_tx-rc-check.json', 'w'), indent=1)
