#!/usr/bin/env python3
"""Evidence audit: for every <block>-evidence.json compare each recorded file hash with (a) the file on disk and
(b) the committed (HEAD) version of that file; for an evidence file with uncommitted changes do the same for its
committed version.  Read-only.  Writes freshness2.json."""
import json, subprocess, pathlib, hashlib, re
H = pathlib.Path(__file__).resolve().parent; R = H.parents[1]
P = R / 'projects/programmable_transceiver_platform'
inv = json.loads((H / 'inventory.json').read_text())['blocks']
def git(*a, raw=False):
    r = subprocess.run(['git', *a], cwd=R, capture_output=True)
    return r.stdout if raw else r.stdout.decode(errors='replace')
def sha_b(b): return hashlib.sha256(b).hexdigest()
def head_sha(rel):
    r = subprocess.run(['git', 'show', f'HEAD:{rel}'], cwd=R, capture_output=True)
    return sha_b(r.stdout) if r.returncode == 0 else None
def check(d, evp):
    rows = []
    for kind in ('source_hashes', 'output_hashes', 'artifact_hashes', 'generated_hashes', 'sources', 'outputs', 'hashes', 'netlist_hashes', 'inputs'):
        hs = d.get(kind)
        if not isinstance(hs, dict): continue
        for fn, h in hs.items():
            if isinstance(h, dict): h = h.get('sha256')
            if not isinstance(h, str) or len(h.replace('sha256:', '')) != 64: continue
            h = h.replace('sha256:', '')
            cands = [evp.parent / fn, evp.parent.parent / fn, P / fn, R / fn, evp.parent / pathlib.Path(fn).name, evp.parent.parent / pathlib.Path(fn).name]
            f = next((c for c in cands if c.is_file()), None)
            if f is None: rows.append(dict(file=fn, kind=kind, disk='missing')); continue
            rel = str(f.relative_to(R))
            rows.append(dict(file=pathlib.Path(fn).name, kind=kind, disk=(sha_b(f.read_bytes()) == h), head=(head_sha(rel) == h) if git('ls-files', '--', rel).strip() else None))
    return rows
out = {}
for n, b in inv.items():
    ev = b.get('evidence')
    if not ev: continue
    evp = R / ev['file']
    r = dict(evidence=ev['file'], dirty=bool(ev['dirty']), worktree=check(json.loads(evp.read_text()), evp))
    if ev['dirty']:
        try: r['committed'] = check(json.loads(git('show', 'HEAD:' + ev['file'])), evp)
        except Exception as e: r['committed_error'] = repr(e)[:100]
    out[n] = r
(H / 'freshness2.json').write_text(json.dumps(out, indent=1) + '\n')
LAY = re.compile(r'\.(mag|ext\.spice|lvs\.spice|gds|spice)$')
for n, r in out.items():
    for tag in ('worktree', 'committed'):
        if tag not in r: continue
        lay = [x for x in r[tag] if LAY.search(x['file'])]
        s = ', '.join(f"{x['file']}:{'disk' if x['disk'] is True else 'MISSING' if x['disk']=='missing' else 'DIFF'}{'' if x.get('head') is None else '/head' if x['head'] else '/HEADDIFF'}" for x in lay)
        print(f"{n:14s} {tag:9s}{' (evidence file uncommitted)' if r['dirty'] and tag=='worktree' else ''} | {s}")
