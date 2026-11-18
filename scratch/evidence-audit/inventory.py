#!/usr/bin/env python3
"""Evidence audit, step 1: inventory of published blocks + cheap checks (no tools run, read-only).
Published = bound by integration/top/masters.txt to a netlist file, or registered in
verification/kl_block_drc_blocks.json, or in the signoff-gap read-back LVS inventory.
Writes scratch/evidence-audit/inventory.json.   Usage: python3 inventory.py
"""
import json, hashlib, subprocess, pathlib, re, time, os
REPO = pathlib.Path(__file__).resolve().parents[2]
PR = 'projects/programmable_transceiver_platform/'
P = REPO / PR
A = PR + 'analog/'
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
def git(*a):
    return subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True).stdout
dirty = {l[3:].strip(): l[:2] for l in git('status', '--porcelain').splitlines()}
def last_commit(paths):
    """(iso date, short hash) of the newest commit touching any of the paths."""
    paths = [p for p in paths if p]
    if not paths: return None
    o = git('log', '-1', '--format=%cI %h', '--', *paths).strip()
    return o.split() if o else None
def tracked(p):
    return bool(git('ls-files', '--', p).strip())

reg = json.loads((P / 'verification/kl_block_drc_blocks.json').read_text())['blocks']
inv = json.loads((REPO / 'scratch/integration/signoff-gap/lvs/blocks.json').read_text())
masters = {}
for l in (P / 'integration/top/masters.txt').read_text().splitlines():
    t = l.split()
    if len(t) < 3 or t[0] != 'master': continue
    kind = t[2] if t[2] in ('inline', 'demand', 'target', 'staged') else 'published'
    ref = t[3] if kind == 'staged' else t[2] if kind == 'published' else None
    if ref:
        path, cell = ref.split(':')
        path = path.replace('A/', A, 1).replace('IS/', 'scratch/island-support-20261108-075605/', 1).replace('IF/', 'scratch/iso-family/', 1)
        masters[t[1]] = dict(kind=kind, ref=path, refcell=cell)
    else:
        masters[t[1]] = dict(kind=kind)

blocks = {}
def add(name, gds, top, ref=None, refcell=None, src=''):
    key = (gds, top)
    for b in blocks.values():
        if (b['gds'], b['top']) == key:
            b['src'] += '+' + src
            if ref and not b.get('ref'): b.update(ref=ref, refcell=refcell)
            if src == 'kldrc-registry': b['kldrc_name'] = name
            return
    blocks[name if name not in blocks else name + '@' + src] = dict(gds=gds, top=top, ref=ref, refcell=refcell, src=src,
                                                                   kldrc_name=name if src == 'kldrc-registry' else None)
for n, v in reg.items(): add(n, v['gds'], v['top'], src='kldrc-registry')
for b in inv: add(b['name'], b['gds'], b['top'], b['ref'], b['refcell'], 'rb-lvs-inventory')
# masters that bind a netlist: attach master state and reference where the top cell / name agrees
for mname, m in masters.items():
    if 'ref' not in m: continue
    hit = [b for n, b in blocks.items() if b['top'] == mname or n == mname or b['top'] == m['refcell']]
    if not hit:
        blocks[mname] = dict(gds=None, top=mname, ref=m['ref'], refcell=m['refcell'], src='masters', kldrc_name=None)
        hit = [blocks[mname]]
    for b in hit:
        b['master'] = mname; b['master_kind'] = m['kind']; b['master_ref'] = m['ref']
        if not b.get('ref'): b.update(ref=m['ref'], refcell=m['refcell'])
demand = sorted(k for k, m in masters.items() if m['kind'] == 'demand')

for name, b in blocks.items():
    g = REPO / b['gds'] if b['gds'] else None
    fam = None
    if b['gds'] and b['gds'].startswith(A):
        fam = b['gds'][len(A):].split('/generated')[0].split('/gds/')[0]
    elif b.get('ref', '') and b['ref'].startswith(A):
        fam = b['ref'][len(A):].split('/generated')[0]
    b['family'] = fam
    b['gds_exists'] = bool(g and g.exists())
    if b['gds_exists']:
        b['gds_sha256'] = sha(g); b['gds_mtime'] = time.strftime('%Y-%m-%dT%H:%M', time.localtime(g.stat().st_mtime)); b['gds_mb'] = round(g.stat().st_size / 1e6, 2)
    if b.get('ref'):
        r = REPO / b['ref']
        b['ref_exists'] = r.exists(); b['ref_tracked'] = tracked(b['ref'])
        if r.exists(): b['ref_mtime'] = time.strftime('%Y-%m-%dT%H:%M', time.localtime(r.stat().st_mtime))
    # records next to the GDS
    if g:
        stem = b.get('kldrc_name') or re.sub(r'\.gds(\.gz)?$', '', g.name)
        short = re.sub(r'\.gds(\.gz)?$', '', g.name)
        kl = [g.parent / f'{s}-kldrc.json' for s in dict.fromkeys([stem, short, name])]
        kl = next((k for k in kl if k.exists()), None)
        if kl is None and b['gds_exists']:   # a record stored under another name: accept it when its hash is this GDS
            for k in sorted(g.parent.glob('*kldrc*.json')):
                try:
                    if json.loads(k.read_text()).get('gds_sha256') == b['gds_sha256']: kl = k; break
                except Exception: pass
        if kl:
            d = json.loads(kl.read_text())
            b['kldrc'] = dict(file=str(kl.relative_to(REPO)), clean=d.get('clean'), sha_matches_gds=(d.get('gds_sha256') == b.get('gds_sha256')),
                              totals={k: v.get('total') for k, v in (d.get('decks') or {}).items()}, klayout=d.get('klayout'),
                              commit=last_commit([str(kl.relative_to(REPO))]), dirty=dirty.get(str(kl.relative_to(REPO))))
        ev = [g.parent / f'{s}-evidence.json' for s in dict.fromkeys([short, stem, name])]
        ev = next((e for e in ev if e.exists()), None)
        if ev:
            d = json.loads(ev.read_text())
            rel = str(ev.relative_to(REPO))
            e = dict(file=rel, commit=last_commit([rel]), dirty=dirty.get(rel), keys=sorted(d)[:40],
                     tests={k: (v.get('state') or v.get('status')) if isinstance(v, dict) else v for k, v in (d.get('tests') or {}).items()})
            stale, ok, missing = [], 0, []
            for kind in ('source_hashes', 'output_hashes', 'artifact_hashes', 'sources', 'outputs', 'hashes'):
                hs = d.get(kind)
                if not isinstance(hs, dict): continue
                for fn, h in hs.items():
                    if isinstance(h, dict): h = h.get('sha256')
                    if not isinstance(h, str) or len(h.replace('sha256:', '')) != 64: continue
                    cands = [ev.parent / fn, ev.parent.parent / fn, P / fn, REPO / fn, ev.parent / pathlib.Path(fn).name, ev.parent.parent / pathlib.Path(fn).name]
                    f = next((c for c in cands if c.is_file()), None)
                    if f is None: missing.append(f'{kind}:{fn}'); continue
                    if sha(f) == h.replace('sha256:', ''): ok += 1
                    else: stale.append(f'{kind}:{fn}' + (' [dirty]' if dirty.get(str(f.relative_to(REPO))) else ''))
            e.update(hash_ok=ok, hash_stale=stale, hash_missing=missing)
            b['evidence'] = e
        lv = [g.parent / f'{s}-lvs.txt' for s in dict.fromkeys([short, stem, name])]
        lv = next((x for x in lv if x.exists()), None)
        if lv:
            t = lv.read_text(errors='replace')
            m = re.search(r'Final result:?\s*(.*)', t)
            b['lvs_record'] = dict(file=str(lv.relative_to(REPO)), final=(m.group(1).strip()[:80] if m else t.strip()[-80:]),
                                   commit=last_commit([str(lv.relative_to(REPO))]), dirty=dirty.get(str(lv.relative_to(REPO))))
(REPO / 'scratch/evidence-audit/inventory.json').write_text(json.dumps(dict(blocks=blocks, demand_masters=demand, n_dirty=len(dirty)), indent=1) + '\n')
print(len(blocks), 'blocks;', sum(1 for b in blocks.values() if b['gds_exists']), 'with GDS on disk;', sum(1 for b in blocks.values() if 'evidence' in b), 'with evidence json;',
      sum(1 for b in blocks.values() if 'kldrc' in b), 'with kldrc record')
