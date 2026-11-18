#!/usr/bin/env python3
"""Evidence audit, second LVS pass on the read-back netlists kept by rb_lvs2.py (no Magic run, netgen only).
 A. read-back vs the COMMITTED schematic (git HEAD, local includes inlined; converters get the standard-cell
    library), with antenna diodes (diode_nd2ps_03v3, added by the layout generators) removed from both sides
    and counted separately.  Also against the working-tree schematic when it differs from HEAD.
 B. pads whose bound netlist carries the modelled n-well diode (diode_nw2ps_06v0, not a drawn device):
    read-back vs the bound netlist without that line.
Appends to sch-results.jsonl."""
import json, re, subprocess, sys, pathlib, os
H = pathlib.Path(__file__).resolve().parent; R = H.parents[1]
sys.path.insert(0, str(H))
import rb_lvs2 as rb
IMG = rb.CANARY; PDK = rb.PDK[IMG]
STD = R / 'scratch/converters/pdk/gf180mcu_fd_sc_mcu7t5v0.spice'

def head_text(rel):
    r = subprocess.run(['git', 'show', f'HEAD:{rel}'], cwd=R, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

def inline(rel, getter, seen=None):
    seen = seen or set(); t = getter(rel)
    if t is None: return None
    out = []
    for ln in t.splitlines():
        m = re.match(r'\s*\.inc(?:lude)?\s+"?([^"\s]+)"?', ln, re.I)
        if m:
            inc = os.path.normpath(os.path.join(os.path.dirname(rel), m.group(1)))
            if inc not in seen:
                seen.add(inc); sub = inline(inc, getter, seen)
                if sub: out.append(sub)
            continue
        out.append(ln)
    return '\n'.join(out)

def strip_model(text, model):
    keep, n = [], 0
    for ln in rb.joined(text):
        t = ln.split()
        pos = [x for x in t[1:] if '=' not in x]
        if t and t[0][:1].lower() in 'xd' and pos and pos[-1].lower() == model: n += 1; continue
        keep.append(ln)
    return '\n'.join(keep) + '\n', n

def netgen(work, a, acell, b, bcell, out):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '8g', '--user', '1000:1000', '-e', 'HOME=/tmp',
           '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', '--entrypoint', '/bin/sh', IMG, '-c',
           f'netgen -batch lvs "{a} {acell}" "{b} {bcell}" {PDK}/libs.tech/netgen/gf180mcuD_setup.tcl {out}']
    try: subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired: return 'TIMEOUT', False, False
    p = work / out; t = p.read_text(errors='replace') if p.exists() else ''
    f = t[t.rfind('Final result'):].strip()[:200].replace('\n', ' ') if 'Final result' in t else 'no result'
    ok = 'match uniquely' in f and 'property errors' not in f.lower()
    if p.exists() and p.stat().st_size > 1_000_000: p.unlink()
    return f, ok, 'property errors' in t.lower()

def census_diff(a, acell, b, bcell):
    try:
        fa, fb = rb.fold(rb.census(a, acell)), rb.fold(rb.census(b, bcell))
    except Exception as e:
        return None, repr(e)[:120]
    # tolerate the 10 nm rounding of extracted W/L/R/C dimensions: compare with dimensions rounded to 3 significant digits
    def rnd(c):
        out = {}
        for k, n in c.items():
            kk = re.sub(r'=([0-9.e+-]+)', lambda m: '=%.3g' % float(m.group(1)), k); out[kk] = out.get(kk, 0) + n
        return out
    ra, rb_ = rnd(fa), rnd(fb)
    d = {k: [ra.get(k, 0), rb_.get(k, 0)] for k in sorted(set(ra) | set(rb_)) if ra.get(k, 0) != rb_.get(k, 0)}
    return d, None

jobs = json.loads((H / 'lvs-jobs.json').read_text())
only = set(sys.argv[1:])
out = H / 'sch-results.jsonl'
for j in jobs:
    if only and j['name'] not in only: continue
    w = H / 'lvs' / j['name']; rbf = w / 'rb.lvs.spice'
    if not rbf.exists(): continue
    res = dict(name=j['name'])
    rbt = rbf.read_text(errors='replace')
    if j.get('sch'):
        rel, cell = j['sch'].rsplit(':', 1)
        variants = [('head', inline(rel, head_text))]
        wt = inline(rel, lambda p: (R / p).read_text(errors='replace') if (R / p).is_file() else None)
        res['schematic_dirty'] = variants[0][1] != wt
        if res['schematic_dirty']: variants.append(('worktree', wt))
        for tag, st in variants:
            if st is None: res[tag] = dict(error='schematic not in HEAD'); continue
            st = rb.strip_parasitics(st)
            if j.get('fam') == 'converters' and STD.exists(): st = STD.read_text() + '\n' + st
            s2, ns = strip_model(st, 'diode_nd2ps_03v3'); r2, nr = strip_model(rbt, 'diode_nd2ps_03v3')
            (w / f'sch_{tag}.spice').write_text(s2); (w / 'rb_nodiode.spice').write_text(r2)
            d, e = census_diff(s2, cell, r2, j['top'])
            f, ok, prop = netgen(w, 'rb_nodiode.spice', j['top'], f'sch_{tag}.spice', cell, f'lvs_sch_{tag}.txt')
            try:
                na = sum(n for k, n in rb.fold(rb.census(rb.strip_parasitics(st), cell)).items() if k.startswith('diode_nd2ps_03v3'))
                nb = sum(n for k, n in rb.fold(rb.census(rbt, j['top'])).items() if k.startswith('diode_nd2ps_03v3'))
            except Exception: na = nb = None
            res[tag] = dict(netgen=f, unique=ok, property_errors=prop, census_equal=(d == {}) if d is not None else None,
                            census_diff=dict(list((d or {}).items())[:8]), census_error=e, antenna_diodes_schematic=na, antenna_diodes_layout=nb)
            for fn in (f'sch_{tag}.spice', 'rb_nodiode.spice'): (w / fn).unlink(missing_ok=True)
    if j['name'] in ('pad_hspad', 'pad_refpad', 'pad_txpad', 'pad_wirepad'):
        ref = rb.strip_parasitics((R / j['ref']).read_text(errors='replace'))
        r2, n = strip_model(ref, 'diode_nw2ps_06v0')
        (w / 'ref_nowell.spice').write_text(r2)
        d, e = census_diff(r2, j['refcell'], rbt, j['top'])
        f, ok, prop = netgen(w, 'rb.lvs.spice', j['top'], 'ref_nowell.spice', j['refcell'], 'lvs_nowell.txt')
        res['nowell'] = dict(removed_model_diodes=n, netgen=f, unique=ok, property_errors=prop, census_equal=(d == {}) if d is not None else None, census_diff=d)
        (w / 'ref_nowell.spice').unlink(missing_ok=True)
    with open(out, 'a') as fo: fo.write(json.dumps(res) + '\n')
    print(json.dumps(res)[:400], flush=True)
print('SCH PASS DONE')
