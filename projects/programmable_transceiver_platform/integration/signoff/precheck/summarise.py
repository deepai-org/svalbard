#!/usr/bin/env python3
"""Summarise a run_precheck.sh work directory: per step status/runtime/metric and per-rule violation counts.
  summarise.py <workdir> [--prune]     writes <workdir>/summary.json, prints a short text table.
--prune deletes the bulky intermediates after counting (lyrdb reports, intermediate GDS, masked.gds, .mag views,
render PNG is kept). Standard library only."""
import collections, glob, json, os, re, sys
import xml.etree.ElementTree as ET
GATING = {  # step id -> how it gates (read from precheck.py 1.7.4 and LibreLane 3.1.0.dev3 step classes)
 'KLayout.ReadLayout': 'gating: unreadable layout aborts', 'KLayout.CheckTopLevel': 'gating, immediate',
 'KLayout.CheckSize': 'gating, immediate', 'KLayout.CheckPadMask': 'gating, immediate (--cob only)',
 'KLayout.GenerateID': 'gating, immediate (ID cells/placement, --cob)', 'KLayout.Render': 'not a check',
 'KLayout.Density': 'produces metric', 'Checker.KLayoutDensity': 'gating, deferred (flow continues, fails at end)',
 'KLayout.ZeroAreaPolygons': 'produces metric', 'Checker.KLayoutZeroAreaPolygons': 'gating, immediate',
 'KLayout.Antenna': 'produces metric', 'Checker.KLayoutAntenna': 'gating, deferred',
 'Magic.DRC': 'produces metric', 'Checker.MagicDRC': 'NOT gating (ERROR_ON_MAGIC_DRC=False: warning only)',
 'KLayout.DRC': 'produces metric', 'Checker.KLayoutDRC': 'gating, deferred', 'KLayout.WriteLayout': 'writes output layout'}
def lyrdb_counts(p):
    c = collections.Counter()
    for _, el in ET.iterparse(p):
        if el.tag == 'item':
            c[(el.findtext('category') or '').strip("'").split(':')[0].strip("' ")] += 1; el.clear()
    return dict(sorted(c.items()))
def magic_counts(p):
    c = collections.Counter(); cur = None; lines = open(p, errors='replace').read().splitlines()
    for i, l in enumerate(lines[2:], 2):
        if l.startswith('[INFO]'): break
        if re.match(r'^ -?[\d.]+um ', l):
            if cur: c[cur] += 1
        elif l.strip() and not l.startswith('---'): cur = l.strip()
    return dict(sorted(c.items()))
def main():
    wd = sys.argv[1]; prune = '--prune' in sys.argv
    rd = os.path.join(wd, 'runs', 'precheck'); out = {'workdir': os.path.abspath(wd), 'steps': []}
    try: out['exit_code'] = int(open(os.path.join(wd, 'exit_code')).read())
    except Exception: out['exit_code'] = None
    log = open(os.path.join(wd, 'precheck.log'), errors='replace').read() if os.path.exists(os.path.join(wd, 'precheck.log')) else ''
    m = re.search(r'SHA256 for \S+:((?:\s+(?:precheck\.py:\d+\s+)?[0-9a-f]+)+)', log)   # the rich log wraps the hash
    out['input_sha256'] = re.sub(r'precheck\.py:\d+|\s', '', m.group(1)) if m else None
    out['completed'] = 'Precheck successfully completed' in log
    metrics = {}
    for sd in sorted(glob.glob(os.path.join(rd, '[0-9]*-*'))):
        s = {'dir': os.path.basename(sd)}
        try: s['id'] = json.load(open(os.path.join(sd, 'config.json')))['meta']['step']
        except Exception: s['id'] = None
        try: s['runtime'] = open(os.path.join(sd, 'runtime.txt')).read().strip()
        except Exception: s['runtime'] = None
        so = os.path.join(sd, 'state_out.json'); s['finished'] = os.path.exists(so)
        if s['finished']:
            new = json.load(open(so)).get('metrics', {})
            s['metrics'] = {k: v for k, v in new.items() if metrics.get(k) != v}; metrics = new
        s['gating'] = GATING.get(s['id'], '?')
        for r in glob.glob(os.path.join(sd, 'reports', '*.lyrdb')):
            if r.endswith('drc.magic.lyrdb'): continue
            s.setdefault('rules', {}).update(lyrdb_counts(r))
        for r in glob.glob(os.path.join(sd, 'reports', 'drc.magic.rpt')):
            s['rules'] = magic_counts(r)
        if not s['finished']: s.pop('rules', None)
        if 'rules' in s: s['total'] = sum(s['rules'].values())
        errs = [l for f in glob.glob(os.path.join(sd, '*.log')) for l in open(f, errors='replace') if re.search(r'\[?Error\]?:|Error:|ERROR', l)]
        if errs: s['errors'] = [e.strip()[:200] for e in errs[:5]]
        out['steps'].append(s)
        if prune:
            for pat in ('reports/*.lyrdb', '*.gds', 'views/*.mag'):
                for f in glob.glob(os.path.join(sd, pat)): os.remove(f)
    out['metrics'] = metrics
    for f in ('error.log', 'warning.log'):
        p = os.path.join(rd, f)
        if os.path.exists(p): out[f] = [l.strip()[:300] for l in open(p, errors='replace') if l.strip()][:40]
    json.dump(out, open(os.path.join(wd, 'summary.json'), 'w'), indent=1)
    print(f"precheck exit {out['exit_code']}  completed={out['completed']}  input sha256 {out['input_sha256']}")
    for s in out['steps']:
        tot = '' if 'total' not in s else f" violations={s['total']}"
        print(f"{s['dir']:38s} {'done' if s['finished'] else 'NOT FINISHED':12s} {s['runtime'] or '':>12s}{tot}  [{s['gating']}]")
        for k, v in s.get('rules', {}).items(): print(f"      {v:8d}  {k[:110]}")
        for e in s.get('errors', []): print('      !', e)
    for l in out.get('error.log', []): print('ERR', l)
if __name__ == '__main__': main()
