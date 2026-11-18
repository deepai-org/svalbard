#!/usr/bin/env python3
"""Evidence audit: KLayout precheck-deck DRC + antenna queue (verification/kl_block_drc.py run(), no --publish),
one block at a time, risk order from drc-jobs.json. Appends to drc-results.jsonl; skips same-hash repeats."""
import json, hashlib, pathlib, sys, os
H = pathlib.Path(__file__).resolve().parent; R = H.parents[1]
os.environ['OMP_NUM_THREADS'] = '1'
sys.path.insert(0, str(R / 'projects/programmable_transceiver_platform/verification'))
import kl_block_drc as K
jobs = json.loads((H / 'drc-jobs.json').read_text())
out = H / 'drc-results.jsonl'
done = {}
if out.exists():
    for l in out.read_text().splitlines():
        try: d = json.loads(l); done[d['block']] = d.get('gds_sha256')
        except Exception: pass
only = set(sys.argv[1:])
for j in jobs:
    if only and j['name'] not in only: continue
    g = R / j['gds']
    if not g.exists(): continue
    if done.get(j['name']) == hashlib.sha256(g.read_bytes()).hexdigest(): continue
    try:
        res = K.run(j['name'], g, j['top'], out=H / 'drc', threads=4, do_publish=False)
        for d in res['decks'].values(): d.pop('cells', None)
    except Exception as e:
        res = dict(block=j['name'], error=repr(e)[:300], clean=None)
    for f in (H / 'drc' / j['name']).glob('*.lyrdb'):
        if f.stat().st_size > 3_000_000: f.unlink()
    with open(out, 'a') as f: f.write(json.dumps(res) + '\n')
print('DRC QUEUE DONE')
