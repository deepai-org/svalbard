#!/usr/bin/env python3
"""GDS read-back LVS (pre-mortem item 3, SG-1).

For one block: copy the PUBLISHED GDS into an empty work directory, read it into a fresh Magic session
(`gds read`, no .mag present), `extract all`, `ext2spice lvs`, then
  (a) netgen LVS (PDK setup, property comparison on) against the reference netlist, and
  (b) an independent flattened device census (model, W, L, nf, m / r_width, r_length / c_width, c_length)
      of read-back vs reference.
Reference = the published netlist the assembly binds (`<block>.ext.spice`, i.e. what was simulated) with the
parasitic C/R lines removed, or `<block>.lvs.spice` when --ref points at one.

  rb_lvs.py NAME GDS TOP REF REFCELL [--work DIR] [--image IMG] [--keep]
Writes DIR/NAME/result.json. Never writes outside --work. The published GDS is only read.
"""
import argparse, gzip, json, re, shutil, subprocess, sys, time
from collections import Counter
from pathlib import Path

CANARY = 'svalbard/librelane-gf180-canary:2026.08'
PDK = {'svalbard/librelane-gf180-canary:2026.08': '/pdk/gf180mcuD'}
PARAMS = ('w', 'l', 'nf', 'm', 'r_width', 'r_length', 'c_width', 'c_length', 'area', 'pj', 'perim')
UNIT = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'meg': 1e6, 'g': 1e9}


def num(s):
    m = re.fullmatch(r'([-+0-9.eE]+)(meg|[fpnumkg])?', s.strip().lower())
    if not m:
        return s
    return float(m.group(1)) * UNIT.get(m.group(2), 1.0)


def joined(text):
    out = []
    for ln in text.splitlines():
        if ln.startswith('+') and out:
            out[-1] += ' ' + ln[1:]
        else:
            out.append(ln)
    return out


def parse(text):
    """-> {subckt: [(kind, model_or_subckt, params)]}; top-level statements under ''."""
    cells, cur = {'': []}, ''
    for ln in joined(text):
        s = ln.strip()
        if not s or s[0] in '*$':
            continue
        lo = s.lower()
        if lo.startswith('.subckt'):
            cur = s.split()[1]
            cells[cur] = []
        elif lo.startswith('.ends'):
            cur = ''
        elif lo[0] == 'x':
            tok = s.split()
            pos = [t for t in tok[1:] if '=' not in t]
            par = {t.split('=')[0].lower(): t.split('=')[1] for t in tok[1:] if '=' in t}
            cells[cur].append(('x', pos[-1], par))
        elif lo[0] in 'mdq':     # primitive with model name as last positional
            tok = s.split()
            pos = [t for t in tok[1:] if '=' not in t]
            par = {t.split('=')[0].lower(): t.split('=')[1] for t in tok[1:] if '=' in t}
            cells[cur].append(('x', pos[-1], par))
    return cells


def census(text, top):
    cells = parse(text)
    lower = {k.lower(): k for k in cells}
    memo = {}

    def flat(c):
        if c in memo:
            return memo[c]
        cnt = Counter()
        for kind, ref, par in cells[c]:
            if ref.lower() in lower and lower[ref.lower()] != c:
                mult = int(round(num(par.get('m', '1')))) if isinstance(num(par.get('m', '1')), float) else 1
                for k, v in flat(lower[ref.lower()]).items():
                    cnt[k] += v * mult
            else:
                key = [ref.lower()]
                for p in PARAMS:
                    if p in par:
                        v = num(par[p])
                        key.append(f'{p}={v:.4g}' if isinstance(v, float) else f'{p}={v}')
                cnt[' '.join(key)] += 1
        memo[c] = cnt
        return cnt
    if top.lower() not in lower:
        raise KeyError(f'top {top} not in netlist ({len(cells)} subckts)')
    return flat(lower[top.lower()])


def fold(cnt):
    """Fold parallel devices: key without m/nf -> total fingers*m, so 2 x (nf=1) == 1 x (nf=2, w doubled is NOT folded)."""
    out = Counter()
    for k, n in cnt.items():
        parts = k.split()
        d = dict(p.split('=') for p in parts[1:])
        m = float(d.pop('m', 1))
        d.pop('nf', None)
        # MOS: total width is w (Magic reports total w with nf); keep w as is, multiply count by m
        out[parts[0] + ' ' + ' '.join(f'{a}={b}' for a, b in sorted(d.items()) if a in ('w', 'l', 'r_width', 'r_length', 'c_width', 'c_length'))] += n * m
    return out


def strip_parasitics(text):
    keep = []
    for ln in joined(text):
        s = ln.lstrip().lower()
        if s[:1] in ('c', 'r') and not s.startswith('.'):
            continue          # extracted lumped parasitics; real R/C devices are X subckt instances in this PDK
        keep.append(ln)
    return '\n'.join(keep) + '\n'


def run(cmd, timeout):
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr, time.time() - t
    except subprocess.TimeoutExpired as e:
        return 124, f'TIMEOUT {timeout}s', time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('gds'); ap.add_argument('top'); ap.add_argument('ref'); ap.add_argument('refcell')
    ap.add_argument('--work', default='/home/ubuntu/svalbard/scratch/integration/signoff-gap/lvs/work')
    ap.add_argument('--image', default=CANARY)
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--timeout', type=int, default=5400)
    ap.add_argument('--cpus', default='2')
    a = ap.parse_args()
    pdk = PDK.get(a.image, '/foss/pdks/gf180mcuD')
    w = Path(a.work) / a.name
    if w.exists():
        shutil.rmtree(w)
    w.mkdir(parents=True)
    res = dict(name=a.name, gds=a.gds, top=a.top, ref=a.ref, refcell=a.refcell, image=a.image)
    src = Path(a.gds)
    if src.suffix == '.gz':
        (w / 'in.gds').write_bytes(gzip.open(src).read())
    else:
        shutil.copy(src, w / 'in.gds')
    (w / 'rb.tcl').write_text('\n'.join([
        'crashbackups stop', 'gds read in.gds', f'load {a.top}', 'select top cell',
        'extract do local', 'extract all', 'ext2spice lvs', 'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
    dk = ['docker', 'run', '--rm', '--network', 'none', '--cpus', a.cpus, '--memory', '12g', '--user', '1000:1000', '-e', 'HOME=/tmp',
          '--mount', f'type=bind,src={w},dst=/work', '-w', '/work']
    sh = '/bin/sh' if a.image == CANARY else '/bin/bash'
    pre = '' if a.image == CANARY else 'export PATH=$PATH:/foss/tools/bin; '
    rc, log, dt = run(dk + ['--entrypoint', sh, a.image, '-c',
                            f'{pre}magic -dnull -noconsole -rcfile {pdk}/libs.tech/magic/gf180mcuD.magicrc /work/rb.tcl'], a.timeout)
    (w / 'magic.log').write_text(log[-200000:])
    res.update(magic_rc=rc, magic_s=round(dt, 1))
    rb = w / 'rb.lvs.spice'
    if not rb.exists() or rb.stat().st_size < 50:
        res.update(status='could_not_run', why=f'Magic read-back produced no netlist (rc {rc}): ' + log[-300:].replace('\n', ' | '))
    else:
        reftext = strip_parasitics(Path(a.ref).read_text(errors='replace'))
        (w / 'ref.spice').write_text(reftext)
        rbtext = rb.read_text(errors='replace')
        # (b) census
        try:
            c_rb, c_ref = census(rbtext, a.top), census(reftext, a.refcell)
            f_rb, f_ref = fold(c_rb), fold(c_ref)
            diff = {k: [f_ref.get(k, 0), f_rb.get(k, 0)] for k in sorted(set(f_rb) | set(f_ref)) if f_rb.get(k, 0) != f_ref.get(k, 0)}
            res.update(devices_ref=int(sum(f_ref.values())), devices_rb=int(sum(f_rb.values())), census_match=not diff,
                       census_exact_match=(c_rb == c_ref), census_diff=dict(list(diff.items())[:40]), census_diff_n=len(diff),
                       models={k: int(v) for k, v in Counter({m: 0 for m in ()}).items()})
            mods = Counter()
            for k, n in f_rb.items():
                mods[k.split()[0]] += n
            res['models'] = {k: int(v) for k, v in sorted(mods.items())}
        except Exception as e:
            res.update(census_match=None, census_error=repr(e)[:300])
        # (a) netgen
        rc2, log2, dt2 = run(dk + ['--entrypoint', sh, a.image, '-c',
                                   f'{pre}netgen -batch lvs "rb.lvs.spice {a.top}" "ref.spice {a.refcell}" {pdk}/libs.tech/netgen/gf180mcuD_setup.tcl lvs.txt'],
                             a.timeout)
        (w / 'netgen.log').write_text(log2[-100000:])
        txt = (w / 'lvs.txt').read_text(errors='replace') if (w / 'lvs.txt').exists() else ''
        final = txt[txt.rfind('Final result'):].strip()[:400] if 'Final result' in txt else ''
        prop = len(re.findall(r'^\S+.*\bcircuit1:.*circuit2:', txt, re.M)) + txt.count('Property mismatch') + len(re.findall(r'There were property errors', txt))
        res.update(netgen_rc=rc2, netgen_s=round(dt2, 1), netgen_final=final,
                   netgen_unique='match uniquely' in final and 'property errors' not in final.lower() and 'mismatch' not in final.lower(),
                   netgen_property_error='property errors' in txt.lower(), netgen_prop_lines=prop)
        if not final:
            res['netgen_tail'] = (txt[-400:] or log2[-400:]).replace('\n', ' | ')
        ok_n, ok_c = res['netgen_unique'], res.get('census_match')
        if ok_n and ok_c:
            res['status'] = 'match'
        elif not final and ok_c is None:
            res.update(status='could_not_run', why='netgen gave no result and census failed')
        else:
            res['status'] = 'mismatch'
            res['what'] = ('netgen: ' + (final or 'no final result')) + ('; census differs' if ok_c is False else '; census equal' if ok_c else '; census n/a')
    (w / 'result.json').write_text(json.dumps(res, indent=1) + '\n')
    if not a.keep:
        for p in w.iterdir():
            if p.name not in ('result.json', 'lvs.txt', 'magic.log', 'netgen.log', 'rb.lvs.spice', 'rb.tcl'):
                p.unlink() if p.is_file() else shutil.rmtree(p)
        for p in (w / 'lvs.txt', w / 'rb.lvs.spice', w / 'magic.log'):
            if p.exists() and p.stat().st_size > 3_000_000:
                p.unlink()
    print(json.dumps({k: res.get(k) for k in ('name', 'status', 'what', 'why', 'devices_ref', 'devices_rb', 'census_match', 'census_diff_n',
                                                'netgen_unique', 'netgen_property_error', 'magic_s', 'netgen_s')}))


if __name__ == '__main__':
    main()
