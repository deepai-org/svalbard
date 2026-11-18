#!/usr/bin/env python3
"""Evidence audit: read-back LVS queue, one block at a time (risk order from lvs-jobs.json).
Appends one JSON line per block to lvs-results.jsonl; skips blocks already done at the same GDS hash."""
import json, subprocess, hashlib, pathlib, sys, os
H = pathlib.Path(__file__).resolve().parent; R = H.parents[1]
os.environ['OMP_NUM_THREADS'] = '1'
jobs = json.loads((H / 'lvs-jobs.json').read_text())
out = H / 'lvs-results.jsonl'
done = {}
if out.exists():
    for l in out.read_text().splitlines():
        try: d = json.loads(l); done[d['name']] = d.get('gds_sha256')
        except Exception: pass
only = set(sys.argv[1:])
for j in jobs:
    if only and j['name'] not in only: continue
    g = R / j['gds']
    if not g.exists(): continue
    if done.get(j['name']) == hashlib.sha256(g.read_bytes()).hexdigest(): continue
    cmd = ['python3', str(H / 'rb_lvs2.py'), j['name'], str(g), j['top'], str(R / j['ref']), j['refcell'], '--work', str(H / 'lvs'), '--cpus', '2']
    if j.get('sch'):
        sp, sc = j['sch'].rsplit(':', 1); cmd += ['--sch', f'{R / sp}:{sc}']
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rp = H / 'lvs' / j['name'] / 'result.json'
    res = json.loads(rp.read_text()) if rp.exists() else dict(name=j['name'], status='could_not_run', why='no result.json')
    with open(out, 'a') as f: f.write(json.dumps(res) + '\n')
print('LVS QUEUE DONE')
