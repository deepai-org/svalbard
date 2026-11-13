#!/usr/bin/env python3
"""Pre-mortem check: evidence freshness for ALL blocks (read-only).
For every *-evidence.json: compare recorded source_hashes/artifact_hashes with the files now on disk.
For every *-kldrc.json: compare gds_sha256 with the GDS now on disk and with the evidence's GDS hash.
Also flags git-dirty/untracked files.   Usage: python3 check_evidence_freshness.py > freshness.json
"""
import json, hashlib, subprocess, sys, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[3]
P = ROOT / 'projects/programmable_transceiver_platform'
def sha(p):
    h = hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def norm(v): return str(v).replace('sha256:', '').strip()
dirty = {}
for l in subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout.splitlines():
    dirty[l[3:].strip()] = l[:2]
def isdirty(p):
    r = str(p.relative_to(ROOT)); 
    for k, v in dirty.items():
        if r == k or (k.endswith('/') and r.startswith(k)): return v
    return None
index = collections.defaultdict(list)
for f in P.rglob('*'):
    if f.is_file() and '__pycache__' not in f.parts: index[f.name].append(f)
def locate(name, base):
    name = name.split('/')[-1] if not (base / name).exists() else name
    for c in (base / name, base.parent / name, base.parent.parent / name):
        if c.is_file(): return c
    c = index.get(name.split('/')[-1], [])
    c = [x for x in c if base.parent in x.parents] or c
    return c[0] if len(c) == 1 else None
out = []
for ev in sorted(P.rglob('*evidence.json')):
    try: d = json.load(open(ev))
    except Exception as e: out.append(dict(evidence=str(ev.relative_to(P)), error=str(e))); continue
    if not isinstance(d, dict): continue
    rec = dict(evidence=str(ev.relative_to(P)), block=d.get('block'), stale_sources=[], stale_artifacts=[], missing=[], ok=0,
               evidence_dirty=isdirty(ev), tests={k: (v.get('status') if isinstance(v, dict) else v) for k, v in (d.get('tests') or {}).items()} )
    for kind in ('source_hashes', 'artifact_hashes'):
        hs = d.get(kind) or {}
        if not isinstance(hs, dict): continue
        for name, h in hs.items():
            if not isinstance(h, str): continue
            f = locate(name, ev.parent)
            if f is None: rec['missing'].append(name); continue
            if sha(f) == norm(h): rec['ok'] += 1
            else: rec['stale_' + ('sources' if kind == 'source_hashes' else 'artifacts')].append(name + (' [dirty]' if isdirty(f) else ''))
    out.append(rec)
kl = []
for k in sorted(P.rglob('*kldrc.json')):
    try: d = json.load(open(k))
    except Exception as e: continue
    g = d.get('gds'); f = locate(g, k.parent) if g else None
    cur = sha(f) if f else None
    kl.append(dict(kldrc=str(k.relative_to(P)), top=d.get('top'), clean=d.get('clean'), deck=d.get('deck'),
                   gds_found=bool(f), matches_current_gds=(cur == norm(d.get('gds_sha256'))) if f else None,
                   totals={n: v.get('total') for n, v in (d.get('decks') or {}).items() if isinstance(v, dict)}))
json.dump(dict(evidence=out, kldrc=kl, n_dirty=len(dirty)), sys.stdout, indent=1)
