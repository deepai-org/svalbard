#!/usr/bin/env python3
"""Main (ring-clocked) RX data path with the REAL slicer: 8 ring phases -> pt_slicer (extracted) ->
pt_wrx_cap (extracted) -> DW/EW, quarter rate.

Why (2026-11-10, capture r5): run_capture.py drives the capture with ideal sampler outputs S_j that change a
fixed d_lat after their phase edge; the real slicer's clock-to-output delay (0.47-0.95 ns tt, 1.24-1.63 ns ss)
moves with corner and rate, which is what the RCS re-capture select exists for.  This bench closes that gap for
the CDR (quarter-rate) path: ideal ring phases CKP0..7 (the ring, ptrim and their jitter are not included),
extracted slicer and capture, PRBS7 line at 4 bits per ring cycle, +/-vd/2 around 1.0 V through 25 ohm/50 fF.
Line phase: every bit boundary lies 0.25 UI before an edge sampler (the clock-late side, as in capture.bench), so
data samplers sit 0.75 UI into their bit and edge samplers 0.25 UI into the next bit (EW_k = bit k+1; the PD votes
UP on every transition).  Judged with capture.bench's own analysis (data, edge, PD votes, 40-bit DX words).

Pass per rate/corner: >= 150 data bits, 0 DW errors, 0 EW errors, PD and gear checks (capture.bench).
Per rate: one RCS value must pass at every envelope corner run for that rate (RCS is a static per-rate setting).

usage: run_capture_rs.py [--only TAG ...] [--jobs N] [--assess-only] [--cap PATH] [--slicer PATH]
"""
import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture  # noqa: E402
import sims  # noqa: E402
import wrx_flow as f  # noqa: E402

SCRATCH = capture.SCRATCH.parent / 'capture_rs'
ENV = dict(tt=dict(corner='typical', temp=27, vdd=3.3), ss=dict(corner='ss', temp=32, vdd=3.15),
           ff=dict(corner='ff', temp=22, vdd=3.35))
CASES = [(f'rs{int(fr / 1e6)}_{c}_r{r}', dict(f=fr, rcs=r, **ENV[c]))
         for fr in (480e6, 625e6, 810e6, 834e6) for c in ('tt', 'ss', 'ff') for r in (0, 1)]
MIN_BITS = 150


def bench(slicer_sub, f=625e6, words=10, vd=0.2, vdd=3.3, corner='typical', temp=27, rcs=0):
    T = 1 / f
    ui = T / 4
    # capture.bench builds the reference stream, LDE, controls, loads and the analysis; only the S_j sources
    # are replaced by the slicer, which samples the line below
    body, ctl, an = capture.bench(4, f=f, words=words, corner=corner, temp=temp, vdd=vdd, rcs=rcs)
    keep = [l for l in body.splitlines() if not re.match(r'VS\d ', l)]
    ncyc = 5 * words + 12
    bits = capture.prbs(int(ncyc * 4) + 64)
    t0 = 2e-9
    # bit m occupies [t0 + (m - 0.75) ui, t0 + (m + 0.25) ui): data sampler (phase 2(m%4)) at t0 + m ui
    pp, pn = [(0, 1.0 - vd / 2)], [(0, 1.0 + vd / 2)]
    for m in range(len(bits) - 1):
        ts = t0 + (m - 0.75) * ui
        if ts < 0:
            continue
        v = vd / 2 if bits[m] else -vd / 2
        pp += [(ts, pp[-1][1]), (ts + 30e-12, 1.0 + v)]
        pn += [(ts, pn[-1][1]), (ts + 30e-12, 1.0 - v)]
        if ts > t0 + ncyc * T:
            break
    L = keep + [f'VIP inps 0 {capture.sims_pwl(pp)}', f'VIN inns 0 {capture.sims_pwl(pn)}',
                'RSP inps inp 25', 'RSN inns inn 25', 'CSP inp 0 50f', 'CSN inn 0 50f']
    sm = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='en', SL_P='inp', SL_N='inn', QCK='qck',
              D0='s0', E0='s1', D1='s2', E1='s3', D2='s4', E2='s5', D3='s6', E3='s7')
    sm.update({f'CKP{k}': f'ckp{k}' for k in range(8)})
    sm.update({p: '0' for p in slicer_sub.ports if p.startswith('trim_')})
    L.append(sims.inst(slicer_sub, sm, 'XSL'))
    L.append('CQCK qck 0 20f')
    return '\n'.join(L), ctl, an


def run(tag, kw, cap_net, sl_net, assess_only=False):
    work = SCRATCH / tag
    work.mkdir(parents=True, exist_ok=True)
    if not assess_only:
        shutil.copy(sl_net, work / 'sl.spice')
        shutil.copy(cap_net, work / 'cap.spice')
    sl = f.parse_spice(work / 'sl.spice')
    sl = sl.get('pt_slicer') if isinstance(sl, dict) else sl
    body, ctl, an = bench(sl, **kw)
    if not assess_only:
        (work / 'tb.cir').write_text('\n'.join([f'* {tag}', sims.sim_header(kw.get('corner', 'typical'), kw.get('temp', 27)),
                                               '.include sl.spice', '.include cap.spice', body, '.control', ctl,
                                               '.endc', '.end']))
        log = f.ngspice(work, 'tb.cir', timeout=8 * 3600)
    else:
        log = (work / 'tb.cir.log').read_text()
    try:
        r = an(log, work / 'out.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    r.update(tag=tag, **kw, slicer_sha256=f.sha256(work / 'sl.spice'), cap_sha256=f.sha256(work / 'cap.spice'))
    r['pass'] = bool(r.get('pass_') and (r.get('bits') or 0) >= MIN_BITS)
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    print(tag, {k: r.get(k) for k in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'gear_ok', 'i_mA', 'pass', 'error')},
          flush=True)
    return tag, r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--assess-only', action='store_true')
    ap.add_argument('--cap', default=str(HERE / 'generated' / 'wrx_cap.ext.spice'))
    ap.add_argument('--slicer', default=str(HERE / 'generated' / 'slicer.ext.spice'))
    a = ap.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    store = SCRATCH / 'results.json'
    res = json.loads(store.read_text()) if store.exists() else {}
    jobs = [(t, k) for t, k in CASES if not a.only or t in a.only]
    with ThreadPoolExecutor(a.jobs) as ex:
        for tag, r in ex.map(lambda j: run(*j, a.cap, a.slicer, assess_only=a.assess_only), jobs):
            res[tag] = r
            store.write_text(json.dumps(res, indent=1, default=str))
    rates = {}
    for fr in (480, 625, 810, 834):
        run_c = [c for c in ENV if any(f'rs{fr}_{c}_r{r}' in res for r in (0, 1))]
        good = [r for r in (0, 1) if run_c and all(res.get(f'rs{fr}_{c}_r{r}', {}).get('pass') for c in run_c)]
        rates[f'{fr}MHz'] = dict(corners_run=run_c, rcs_passing=good, pass_=bool(good))
    (SCRATCH / 'summary.json').write_text(json.dumps(rates, indent=1) + '\n')
    print(json.dumps(rates), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
