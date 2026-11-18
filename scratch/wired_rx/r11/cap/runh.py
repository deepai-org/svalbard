"""Capture-only benches (capture.bench: ideal ring phases, ideal sampler outputs) on HOST ngspice with KLU; same decks and
the same analysis as run_capture.py / r10cap/rune.py, which use the docker ngspice (3-4x slower).
  runh.py CAPNET STORE case[@V] ...        case = a run_capture.CASES tag, or the extra tags below; pess_<case>, neg_s2stuck
Run through ../../slot.sh (one case per call)."""
import sys, json, re, os, subprocess, time
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10ctle'); sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10cap')
import lib10 as L
import stagee, capture as c, run_capture as rc
H = Path(__file__).resolve().parent
cases = {t: (b, k) for t, b, k in rc.CASES}
cases['safes_q625'] = (4, dict(f=625e6, words=4, en_off=True, s_static=True))
for nn in (50, 55, 60, 65, 70, 75, 80, 90, 100, 120): cases[f'q625_lde{nn}'] = (4, dict(f=625e6, words=12, lde_delay=nn * 1e-11))
SS = dict(corner='ss', temp=32, vdd=3.15); FF = dict(corner='ff', temp=22, vdd=3.35)
cases.update({'q675_r1': (4, dict(f=675e6, words=12, rcs=1, d_lat=0.47e-9)), 'q675_ss_r1': (4, dict(f=675e6, words=12, rcs=1, d_lat=0.47e-9, **SS)),
              'f480p0_ss': (1, dict(f=480e6, words=8, psel=0, **SS)), 'f480p3_ss': (1, dict(f=480e6, words=8, psel=3, **SS)), 'f480p5_ss': (1, dict(f=480e6, words=8, psel=5, **SS)),
              'f480p0_ff': (1, dict(f=480e6, words=8, psel=0, **FF)), 'h625_ss': (2, dict(f=625e6, words=12, **SS)), 'h625_ss_r1': (2, dict(f=625e6, words=12, rcs=1, d_lat=0.47e-9, **SS)),
              'q625_ff_r1': (4, dict(f=625e6, words=12, rcs=1, d_lat=0.327e-9, **FF)), 'q810_ff_r1': (4, dict(f=810e6, words=12, rcs=1, d_lat=0.327e-9, **FF))})
for p in range(8): cases[f'f480p{p}'] = (1, dict(f=480e6, words=8, psel=p))
CK = {('typical', 27): 'tt', ('ss', 32): 'ss315', ('ff', 22): 'ff'}


def run(capnet, store, spec):
    vov = None; tag0 = spec
    if '@' in spec: spec, vov = spec.split('@'); vov = float(vov)
    neg = spec == 'neg_s2stuck'; pess = spec.startswith('pess_')
    tag = 'q625' if neg else spec.split('_', 1)[1] if pess else spec
    b, k = cases[tag]; k = dict(k)
    if neg: k['words'] = 8
    if vov: k['vdd'] = vov
    body, ctl, an = c.bench(b, **k)
    if neg:
        body = re.sub(r'^VS2 s2 0 .*$', 'VS2 s2 0 0', body, flags=re.M); assert 'VS2 s2 0 0' in body
    net = L.net('wrx_cap', str(capnet), 'pess' if pess else 'nom')
    corner, temp = k.get('corner', 'typical'), k.get('temp', 27)
    key = tag0.replace('@', '_v')
    run_ = H / 'run'; run_.mkdir(exist_ok=True)
    hdr = [f'* capture {key}', '.option klu', f'.include {L.PDK}/design.ngspice', f'.lib {L.PDK}/sm141064.ngspice {corner}', f'.lib {L.PDK}/sm141064.ngspice res_{corner}', f'.lib {L.PDK}/sm141064.ngspice diode_{corner}',
           f'.option temp={temp} gmin=1e-12 reltol=1e-3', f'.include {net}']
    ctl = ctl.replace('wrdata out.txt', f'wrdata {key}.txt')
    (run_ / f'{key}.cir').write_text('\n'.join(hdr + [body, '.control', ctl, '.endc', '.end']) + '\n')
    t0 = time.time()
    p = subprocess.run(['ngspice', '-b', f'{key}.cir'], cwd=run_, capture_output=True, text=True, timeout=6 * 3600, env=dict(os.environ, OMP_NUM_THREADS='1'))
    log = p.stdout + p.stderr
    try: r = an(log, run_ / f'{key}.txt')
    except Exception as e: r = dict(error=repr(e)[:300], log_tail=log[-300:])
    for f_ in (run_ / f'{key}.txt', run_ / f'{key}.cir'):
        if f_.exists(): f_.unlink()
    r = json.loads(json.dumps(r, default=float))
    r.update(case=key, netlist=str(capnet), netlist_sha256=L.sha(capnet), bound='pess' if pess else 'nom', seconds=round(time.time() - t0), solver='host ngspice-42 klu', **{kk: vv for kk, vv in k.items()})
    if k.get('en_off'): r['pass'] = bool(r.get('pass_'))
    elif neg: r['pass'] = bool(r.get('pass_')); r['expected'] = 'fail (control)'
    else: r['pass'] = bool(r.get('pass_') and (r.get('bits') or 0) >= rc.MIN_BITS[b] and r.get('bit_errors') == 0)
    S = Path(store); D = json.loads(S.read_text()) if S.exists() else {}
    D[key] = r; S.write_text(json.dumps(D, indent=1))
    print(key, {x: r.get(x) for x in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'gear_ok', 'strobe_word_errors', 'i_mA', 'i_uA', 'pass', 'error', 'seconds')}, flush=True)


if __name__ == '__main__':
    for spec in sys.argv[3:]: run(Path(sys.argv[1]).resolve(), sys.argv[2], spec)
