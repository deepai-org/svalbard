#!/usr/bin/env python3
"""WCLK_IN raw-word fallback: external clock -> pt_slicer -> pt_wrx_cap -> DW/EW, extracted.

Fallback contract (README `pt_wrx_cap` contract): CKP0..3 = CK, CKP4..7 = !CK (WCLK_IN through
diff_clk_rx/clockmux; that mux and its skew are integration items, here ideal 50 ps edges).  The
slicer samples the line at both CK edges (D0,E0,D1,E1 at the rise, D2,E2,D3,E3 at the fall); the
capture runs in half mode (B2=1), so DW carries 2 bits per CK cycle (D0 at the rise, D2 at the fall)
and EW the D1/D3 samplers, taken at the same instants (EW must equal DW: a second, independent
sampler per bit).  The line is PRBS7 at 2 bits per CK cycle, +/-vd/2 differential around 1.0 V,
eye centred on the CK edges (the board/FPGA sets that phase in this mode; no CDR).

Pass per case: >= 120 data bits after start-up, 0 DW errors against the aligned PRBS and EW == DW.
Writes generated/wrx_fallback-evidence.json.

usage: run_fallback.py [--only TAG ...] [--jobs N] [--assess-only]
"""
import argparse
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture  # noqa: E402
import sims  # noqa: E402
import wrx_flow as f  # noqa: E402

SCRATCH = capture.SCRATCH.parent / 'fallback'
# W1 (2026-11-10): both re-capture selects at tt and at the slow envelope corner; a rate passes when
# at least one RCS value passes at every corner (RCS is calibrated per rate from raw words)
CASES = [(f'fb{int(fr / 1e6)}_r{r}', dict(f=fr, rcs=r)) for fr in (480e6, 625e6, 810e6) for r in (0, 1)] + \
        [(f'fb{int(fr / 1e6)}_ss_r{r}', dict(f=fr, rcs=r, corner='ss', temp=32, vdd=3.15))
         for fr in (480e6, 625e6, 810e6) for r in (0, 1)] + \
        [('fb625_vd100_r1', dict(f=625e6, vd=0.1, rcs=1))]
MIN_BITS = 120


def bench(slicer_sub, f=625e6, words=12, vd=0.2, vdd=3.3, corner='typical', temp=27, rcs=0):
    T = 1 / f
    ui = T / 2
    nw = 10                                   # half mode: 10 ring cycles per 20-bit word
    ncyc = nw * words + 12
    bits = capture.prbs(2 * ncyc + 64)
    t0 = 2e-9
    tr = 50e-12
    # bit m is centred on CK edge m (even: rise, odd: fall); transitions half a UI before/after
    pp, pn = [(0, 1.0 - vd / 2), ], [(0, 1.0 + vd / 2)]
    for m in range(2 * ncyc + 2):
        ts = t0 + m * ui - ui / 2
        v = vd / 2 if bits[m] else -vd / 2
        pp += [(ts, pp[-1][1]), (ts + 30e-12, 1.0 + v)]
        pn += [(ts, pn[-1][1]), (ts + 30e-12, 1.0 - v)]
    L = [f'VDD vdd 0 {vdd}',
         f'VCK ck 0 PULSE(0 {vdd} {t0 - tr / 2:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})',
         f'VCKN ckn 0 PULSE({vdd} 0 {t0 - tr / 2:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})',
         f'VIP inps 0 {capture.sims_pwl(pp)}', f'VIN inns 0 {capture.sims_pwl(pn)}',
         'RSP inps inp 25', 'RSN inns inn 25', 'CSP inp 0 50f', 'CSN inn 0 50f',
         f'VEN en 0 PWL(0 0 1n 0 1.05n {vdd})', f'VB2 b2 0 {vdd}', 'VB1 b1 0 0',
         f'VRCS rcs 0 {vdd * rcs}', 'VPS0 psel0 0 0', 'VPS1 psel1 0 0', 'VPS2 psel2 0 0', 'VSP slipp 0 0', 'VSM slipm 0 0']
    lde = [(0, 0.)]
    for w in range(words + 2):
        a = t0 + (w * nw + 2) * T + 0.3e-9
        lde += [(a, 0.), (a + 30e-12, vdd), (a + T, vdd), (a + T + 30e-12, 0.)]
    L.append(f'VLDE lde 0 {capture.sims_pwl(lde)}')
    sm = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='en', SL_P='inp', SL_N='inn', QCK='qck',
              D0='s0', E0='s1', D1='s2', E1='s3', D2='s4', E2='s5', D3='s6', E3='s7')
    sm.update({f'CKP{k}': ('ck' if k < 4 else 'ckn') for k in range(8)})
    sm.update({p: '0' for p in slicer_sub.ports if p.startswith('trim_')})
    L.append(sims.inst(slicer_sub, sm, 'XSL'))
    L.append('CQCK qck 0 20f')
    conn = {p: p.lower() for p in capture.TOP_PORTS}
    conn.update({f'CKP{k}': ('ck' if k < 4 else 'ckn') for k in range(8)}, VDD='vdd', VSS='0')
    L.append('XCAP ' + ' '.join(conn[p] for p in capture.TOP_PORTS) + ' pt_wrx_cap')
    L += [f'CDW{i} dw{i} 0 20f' for i in range(20)] + [f'CEW{i} ew{i} 0 20f' for i in range(20)]
    L += [f'CUP{k} up{k} 0 100f' for k in range(4)] + [f'CDN{k} dn{k} 0 100f' for k in range(4)] + \
         [f'CDX{i} dx{i} 0 50f' for i in range(40)] + ['CWC wclk40 0 50f']     # r4 outputs: pin loads
    T_end = t0 + ncyc * T
    outs = ' '.join(f'v(dw{i})' for i in range(20)) + ' ' + ' '.join(f'v(ew{i})' for i in range(20))
    ctl = '\n'.join([f'tran 2p {T_end:.4g} 0 10p', 'set wr_singlescale', f'wrdata out.txt v(lde) {outs}',
                     f'meas tran iavg avg i(VDD) from={t0 + 6 * T:.4g} to={T_end:.4g}'])

    def analyse(log, data):
        d = np.loadtxt(data)
        t = d[:, 0]
        ch = np.zeros(len(t), bool)
        for col in range(2, 42):
            v = d[:, col] > vdd / 2
            ch[1:] |= v[1:] != v[:-1]
        groups = []
        for x in t[ch]:
            if groups and x - groups[-1][-1] < 0.3 * nw * T:
                groups[-1].append(x)
            else:
                groups.append([x])
        up = [g[0] for g in groups]
        ws = []
        for a, b in zip(up, up[1:]):
            if abs(b - a - nw * T) > 0.2 * nw * T:
                continue
            k = int(np.searchsorted(t, (a + b) / 2))
            ws.append(([int(v > vdd / 2) for v in d[k, 2:22]], [int(v > vdd / 2) for v in d[k, 22:42]]))
        ws = ws[2:]
        stream = [b for w, _ in ws for b in w]
        estream = [b for _, e in ws for b in e]
        best = None
        for off in range(len(bits) - len(stream)):
            err = sum(1 for i, b in enumerate(stream) if bits[off + i] != b)
            if best is None or err < best[1]:
                best = (off, err)
        ew_mismatch = sum(1 for a, b in zip(stream, estream) if a != b)
        iavg = None
        for line_ in log.splitlines():
            if line_.strip().startswith('iavg'):
                iavg = -float(line_.split('=')[1].split()[0])
        return dict(words=len(ws), bits=len(stream), offset=best[0] if best else None,
                    bit_errors=best[1] if best else None, ew_vs_dw_mismatch=ew_mismatch,
                    i_mA=iavg * 1e3 if iavg else None,
                    pass_=bool(best and len(stream) >= MIN_BITS and best[1] == 0 and ew_mismatch == 0))
    return '\n'.join(L), ctl, analyse


def run(tag, kw, assess_only=False):
    work = SCRATCH / tag
    work.mkdir(parents=True, exist_ok=True)
    if not assess_only:
        shutil.copy(HERE / 'generated' / 'slicer.ext.spice', work / 'sl.spice')
        shutil.copy(HERE / 'generated' / 'wrx_cap.ext.spice', work / 'cap.spice')
    sl = f.parse_spice(work / 'sl.spice')
    sl = sl.get('pt_slicer') if isinstance(sl, dict) else sl
    body, ctl, an = bench(sl, **kw)
    if not assess_only:
        (work / 'tb.cir').write_text('\n'.join([f'* {tag}', sims.sim_header(kw.get('corner', 'typical'), kw.get('temp', 27)),
                                               '.include sl.spice', '.include cap.spice', body, '.control', ctl,
                                               '.endc', '.end']))
        log = f.ngspice(work, 'tb.cir', timeout=6 * 3600)
    else:
        log = (work / 'tb.cir.log').read_text()
    try:
        r = an(log, work / 'out.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    r.update(tag=tag, **kw, slicer_sha256=f.sha256(work / 'sl.spice'), cap_sha256=f.sha256(work / 'cap.spice'))
    r['pass'] = bool(r.get('pass_'))
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    print(tag, {k: r.get(k) for k in ('words', 'bits', 'bit_errors', 'ew_vs_dw_mismatch', 'i_mA', 'pass', 'error')}, flush=True)
    return tag, r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--assess-only', action='store_true')
    a = ap.parse_args()
    store = SCRATCH / 'results.json'
    res = json.loads(store.read_text()) if (store.exists() and a.only) else {}
    jobs = [(t, k) for t, k in CASES if not a.only or t in a.only]
    with ThreadPoolExecutor(a.jobs) as ex:
        for tag, r in ex.map(lambda j: run(*j, assess_only=a.assess_only), jobs):
            res[tag] = r
            SCRATCH.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps(res, indent=1, default=str))
    # per rate: some single RCS value must pass at tt AND ss/32 C/3.15 V (one static setting per rate)
    rates = {}
    for fr in (480, 625, 810):
        good = [r for r in (0, 1) if all(res.get(t, {}).get('pass') for t in (f'fb{fr}_r{r}', f'fb{fr}_ss_r{r}'))]
        rates[f'{fr}MHz'] = dict(pass_=bool(good), rcs_passing=good)
    ok = all(v['pass_'] for v in rates.values()) and bool(res.get('fb625_vd100_r1', {}).get('pass'))
    hashes = {p: f.sha256(HERE / p) for p in ['run_fallback.py', 'capture.py', 'generated/wrx_cap.ext.spice',
                                              'generated/slicer.ext.spice']}
    ev = dict(block='wrx_fallback', subckt='pt_slicer + pt_wrx_cap', source_hashes=hashes,
              scope='WCLK_IN raw-word fallback, extracted slicer + extracted capture, tt/27C/3.3V and ss/32C/3.15V, both RCS values, ideal CK/!CK on '
                    'CKP0..3/CKP4..7 (the diff_clk_rx/clockmux path and its skew are not included), eye centred '
                    'on the CK edges, half mode (2 bits per CK cycle).',
              criterion='per rate (480/625/810 MHz) one RCS value with 0 DW errors and EW == DW at tt and at ss/32C/3.15V; '
                        'plus fb625_vd100_r1',
              tests=dict(fallback=dict(state='pass' if ok else 'fail', rates=rates,
                                       cases={k: {kk: v.get(kk) for kk in ('f', 'vd', 'rcs', 'corner', 'temp', 'vdd', 'words', 'bits', 'bit_errors',
                                                                             'ew_vs_dw_mismatch', 'i_mA', 'pass', 'error')}
                                              for k, v in sorted(res.items())})))
    (HERE / 'generated' / 'wrx_fallback-evidence.json').write_text(json.dumps(ev, indent=1, default=str) + '\n')
    print('wrx_fallback', ev['tests']['fallback']['state'], flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
