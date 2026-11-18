#!/usr/bin/env python3
"""Evidence audit: evidence age against git history and the files on disk (read-only). Writes freshness.json."""
import json, subprocess, pathlib, re, os, time
H = pathlib.Path(__file__).resolve().parent; R = H.parents[1]
A = 'projects/programmable_transceiver_platform/analog/'
inv = json.loads((H / 'inventory.json').read_text())['blocks']
def git(*a): return subprocess.run(['git', *a], cwd=R, capture_output=True, text=True).stdout
dirty = {l[3:].strip(): l[:2] for l in git('status', '--porcelain').splitlines()}
def last(paths):
    paths = [p for p in paths if p and (R / p).exists()]
    if not paths: return None
    o = git('log', '-1', '--format=%cI %h', '--', *paths).strip().split()
    return o if o else None
out = {}
for n, b in inv.items():
    if n.endswith('@rb-lvs-inventory') or not b.get('gds'): continue
    fam = b.get('family'); r = dict(family=fam)
    g = R / b['gds']; short = re.sub(r'\.gds(\.gz)?$', '', os.path.basename(b['gds']))
    ev = b.get('evidence')
    if g.exists(): r['gds_mtime'] = time.strftime('%Y-%m-%dT%H:%M', time.localtime(g.stat().st_mtime))
    if fam and (R / A / fam).is_dir():
        sp = [A + fam + '/' + short + '.spice', A + fam + '/' + b['top'] + '.spice']
        sp = [s for s in sp if (R / s).exists()]
        r['netlist'] = sp[0] if sp else None
        r['netlist_commit'] = last(sp)
        r['netlist_dirty'] = any(dirty.get(s) for s in sp)
        py = [l for l in git('ls-files', A + fam).splitlines() if l.endswith('.py') and '/generated/' not in l]
        r['family_scripts_commit'] = last(py)
        r['family_scripts_dirty'] = sorted(os.path.basename(p) for p in py if dirty.get(p))
        r['family_untracked'] = sorted(os.path.basename(k) for k, v in dirty.items() if v == '??' and k.startswith(A + fam + '/') and '/generated/' not in k)[:8]
    if ev:
        r['evidence'] = ev['file'].replace(A, ''); r['evidence_commit'] = ev['commit']; r['evidence_dirty'] = ev['dirty']
        r['hash_ok'] = ev['hash_ok']; r['hash_stale'] = ev['hash_stale']; r['hash_missing'] = ev['hash_missing']; r['tests'] = ev['tests']
        ec = ev['commit'][0] if ev['commit'] else None
        r['netlist_newer_than_evidence'] = bool(ec and r.get('netlist_commit') and r['netlist_commit'][0] > ec)
        r['scripts_newer_than_evidence'] = bool(ec and r.get('family_scripts_commit') and r['family_scripts_commit'][0] > ec)
        # GDS written after the evidence commit (local time vs commit time: compare as epoch)
        if ec and g.exists():
            et = int(git('log', '-1', '--format=%ct', '--', ev['file']).strip() or 0)
            r['gds_newer_than_evidence_commit'] = g.stat().st_mtime > et + 60
    out[n] = r
(H / 'freshness.json').write_text(json.dumps(out, indent=1) + '\n')
for n, r in out.items():
    if 'evidence' not in r: print(f"{n:24s} NO EVIDENCE JSON  gds {r.get('gds_mtime')}"); continue
    print(f"{n:24s} ev {r['evidence_commit'][0][:16] if r['evidence_commit'] else '-'} {'DIRTY' if r['evidence_dirty'] else ''} | netlist {r['netlist_commit'][0][:10] if r.get('netlist_commit') else '-'}{'*' if r.get('netlist_dirty') else ''} newer={r.get('netlist_newer_than_evidence')} | scripts {r['family_scripts_commit'][0][:10] if r.get('family_scripts_commit') else '-'} newer={r.get('scripts_newer_than_evidence')} dirty={len(r.get('family_scripts_dirty',[]))} | gds {r.get('gds_mtime')} newer={r.get('gds_newer_than_evidence_commit')} | hash ok/stale {r['hash_ok']}/{len(r['hash_stale'])}: {[s.split(':')[-1] for s in r['hash_stale']][:7]}")
