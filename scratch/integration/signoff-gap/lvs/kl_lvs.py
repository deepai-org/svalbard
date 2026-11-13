#!/usr/bin/env python3
"""Second, independent extractor for the GDS read-back check (SG-1): the PDK KLayout LVS deck
(libs.tech/klayout/tech/lvs/run_lvs.py, variant D) extracts devices straight from the published GDS.
We do not use its own compare (it needs the schematic in its dialect); instead the extracted netlist's
device summary (per model: count, total W per L / total R length per width / total cap area / total diode
area) is compared with the same summary of the reference netlist (Magic format).

  kl_lvs.py NAME GDS TOP REF REFCELL [--work DIR]
"""
import argparse, gzip, json, re, shutil, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rb_lvs import joined, parse, num, strip_parasitics

IMG = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'


def klass(model):
    m = model.lower()
    if 'fet' in m and not m.startswith('cap'):
        return 'mos'
    if m.startswith(('ppoly', 'npoly', 'nplus', 'pplus', 'nwell', 'rm', 'tm')):
        return 'res'
    if m.startswith('cap'):
        return 'cap'
    if m.startswith(('diode', 'sc_diode', 'np_', 'pn_')):
        return 'diode'
    if m.startswith(('pnp', 'npn')):
        return 'bjt'
    return 'other'


def add(summ, model, par, mult=1.0):
    k = klass(model)
    g = lambda *names: next((num(par[n]) for n in names if n in par and isinstance(num(par[n]), float)), None)
    m = (g('m') or 1.0) * mult
    if k == 'mos':
        w, l = g('w'), g('l')
        key = f'{model} l={l*1e6:.3f}u' if l else model
        summ[key]['n'] += m; summ[key]['q'] += (w or 0) * 1e6 * m; summ[key]['unit'] = 'W um'
    elif k == 'res':
        w, l = g('r_width', 'w'), g('r_length', 'l')
        key = f'{model} w={w*1e6:.3f}u' if w else model
        summ[key]['n'] += m; summ[key]['q'] += (l or 0) * 1e6 * m; summ[key]['unit'] = 'L um'
    elif k == 'cap':
        a = g('a', 'area')
        if a is None:
            cw, cl = g('c_width', 'w'), g('c_length', 'l')
            a = (cw or 0) * (cl or 0)
        summ[model]['n'] += m; summ[model]['q'] += a * 1e12 * m; summ[model]['unit'] = 'area um2'
    elif k == 'diode':
        a = g('a', 'area')
        summ[model]['n'] += m; summ[model]['q'] += (a or 0) * 1e12 * m; summ[model]['unit'] = 'area um2'
    else:
        summ[model]['n'] += m; summ[model]['unit'] = 'count'


def summary_magic(text, top):
    cells = parse(text)
    lower = {k.lower(): k for k in cells}
    summ = defaultdict(lambda: dict(n=0.0, q=0.0, unit=''))

    def walk(c, mult, depth=0):
        for _, ref, par in cells[c]:
            if ref.lower() in lower and lower[ref.lower()] != c and depth < 40:
                mm = num(par.get('m', '1'))
                walk(lower[ref.lower()], mult * (mm if isinstance(mm, float) else 1.0), depth + 1)
            else:
                add(summ, ref.lower(), par, mult)
    walk(lower[top.lower()], 1.0)
    return summ


def summary_klayout(text):
    summ = defaultdict(lambda: dict(n=0.0, q=0.0, unit=''))
    cells, cur = {}, None
    for ln in joined(text):
        s = ln.strip()
        if not s or s[0] == '*':
            continue
        if s.lower().startswith('.subckt'):
            cur = s.split()[1]; cells[cur] = []
        elif s.lower().startswith('.ends'):
            cur = None
        elif cur is not None and s[0].upper() in 'MRCDQX':
            tok = s.split()
            pos = [t for t in tok[1:] if '=' not in t]
            par = {t.split('=')[0].lower(): t.split('=')[1] for t in tok[1:] if '=' in t}
            model = pos[-1]
            if s[0].upper() in 'RC' and re.fullmatch(r'[-+0-9.eE]+[a-zA-Z]*', model):
                model = pos[-2] if len(pos) > 3 else model
            cells[cur].append((s[0].upper(), model, par))
    return cells, summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('gds'); ap.add_argument('top'); ap.add_argument('ref'); ap.add_argument('refcell')
    ap.add_argument('--work', default='/home/ubuntu/svalbard/scratch/integration/signoff-gap/lvs/klwork')
    ap.add_argument('--timeout', type=int, default=2700)
    ap.add_argument('--mode', default='deep')
    a = ap.parse_args()
    w = Path(a.work) / a.name
    if w.exists():
        shutil.rmtree(w)
    w.mkdir(parents=True)
    src = Path(a.gds)
    (w / 'in.gds').write_bytes(gzip.open(src).read() if src.suffix == '.gz' else src.read_bytes())
    (w / 'dummy.spice').write_text(f'.subckt {a.top}\n.ends\n')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '16g', '--user', '1000:1000', '-e', 'HOME=/tmp',
           '-v', f'{w}:/work', '-w', '/work', '--entrypoint', '/bin/bash', IMG, '-c',
           'export PATH=$PATH:/foss/tools/bin:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout PDK_ROOT=/foss/pdks PDK=gf180mcuD; '
           f'python3 /foss/pdks/gf180mcuD/libs.tech/klayout/tech/lvs/run_lvs.py --layout=/work/in.gds --netlist=/work/dummy.spice '
           f'--variant=D --topcell={a.top} --run_dir=/work/run --run_mode={a.mode} --thr=1 --net_only 2>&1 | tail -40']
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
        log = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        log = 'TIMEOUT'
    res = dict(name=a.name, gds=a.gds, top=a.top, ref=a.ref, seconds=round(time.time() - t, 1), mode=a.mode)
    cir = next(iter((w / 'run').glob('*.cir')), None) if (w / 'run').exists() else None
    if cir is None:
        res.update(status='could_not_run', why=log[-400:].replace('\n', ' | '))
    else:
        cells, _ = summary_klayout(cir.read_text(errors='replace'))
        lower = {k.lower(): k for k in cells}
        summ = defaultdict(lambda: dict(n=0.0, q=0.0, unit=''))

        def walk(c, mult, depth=0):
            for kind, model, par in cells[c]:
                if kind == 'X' and model.lower() in lower and depth < 40:
                    walk(lower[model.lower()], mult, depth + 1)
                else:
                    add(summ, model.lower(), par, mult)
        topc = lower.get(a.top.lower()) or max(cells, key=lambda c: len(cells[c]))
        walk(topc, 1.0)
        ref = summary_magic(strip_parasitics(Path(a.ref).read_text(errors='replace')), a.refcell)
        diff = {}
        for k in sorted(set(summ) | set(ref)):
            x, y = summ.get(k, dict(n=0, q=0)), ref.get(k, dict(n=0, q=0))
            tol = 0.005 * max(abs(x['q']), abs(y['q']), 1e-9)
            if abs(x['q'] - y['q']) > tol or (x['q'] == 0 and y['q'] == 0 and x['n'] != y['n']):
                diff[k] = dict(ref_n=y['n'], kl_n=x['n'], ref_q=round(y['q'], 3), kl_q=round(x['q'], 3))
        res.update(status='match' if not diff else 'mismatch', diff=dict(list(diff.items())[:30]), diff_n=len(diff),
                   kl_summary={k: [v['n'], round(v['q'], 3), v['unit']] for k, v in sorted(summ.items())},
                   kl_devices=int(sum(v['n'] for v in summ.values())), ref_devices=int(sum(v['n'] for v in ref.values())))
    (w / 'result.json').write_text(json.dumps(res, indent=1) + '\n')
    for p in w.iterdir():
        if p.name != 'result.json':
            p.unlink() if p.is_file() else shutil.rmtree(p)
    print(json.dumps({k: res.get(k) for k in ('name', 'status', 'why', 'diff_n', 'kl_devices', 'ref_devices', 'seconds')}), json.dumps(res.get('diff', {}))[:500])


if __name__ == '__main__':
    main()
