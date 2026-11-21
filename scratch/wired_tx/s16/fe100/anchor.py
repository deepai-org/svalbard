"""Full-chain 100BASE-TX anchor: extracted pt_wiredtx8 (net/pt_wiredtx8.fullfix16.rc.spice, fixcap16) driven by its real ring
(extracted pt_pll_ring_core, open loop, s12 tune, route 30 ohm / 75 fF), pad RT or C (termination OFF), COB bond, B39, magnetics,
100 ohm at the RJ45. Line = MLT-3 of scrambled idle at 125 MBd, ring 312.5 MHz -> 2.5 Gb/s core, n = 20 core bits per symbol.

    python3 anchor.py '{"tag":"A_ssp_255_pol1","corner":"ss","pess":true,"vdd":3.15,"code":255,"pol":1,"pad_model":"RT","nsym":26}'
"""
import sys, json, time, hashlib
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent))
import chain16
from chain14 import C13
from chain13 import tools, S, I
import net100, stream

RES = H / 'results'; RUNS = H / 'runs'
VRING = dict(ss=2.69, typical=2.95, ff=3.01)
TEMP = dict(ss=32, typical=27, ff=22)
RATE = 2.5e9; N = 20; START = 1100     # stream window (stream.py): scored part has the longest +1 hold (12 symbols) of the stream

_orig_pkg = I.pkg_chain


def _pkg(pk, *a, **k):
    r = _orig_pkg(pk, *a, **k); pk[:] = net100.board(pk); return r


I.pkg_chain = _pkg


def deck(w, **kw):
    names = C13.deck(w, **kw)
    if kw.get('full'):
        p = w / 'tb.sp'; t = p.read_text().split('\n'); vdd = kw['vdd']
        for i, l in enumerate(t):
            if l.startswith('VTE TERM_ENABLE'):
                t[i] = 'VTE TERM_ENABLE 0 0'
            if l.startswith(('save ', 'wrdata ')):
                t[i] = l.replace('v(FAR_P)', 'v(BOARD_P)').replace('v(FAR_N)', 'v(BOARD_N)') + ' i(VILP) i(VILN)'
        p.write_text('\n'.join(t)); names = names + ['ILP', 'ILN']
    return names


def measure(t, w, sy, ts, t_first, vdd):
    """fit the symbol train (lag search) on RJ diff; settled levels = symbol centres from the 2nd symbol of each hold on."""
    v = w['RJ_P'] - w['RJ_N']
    best = None
    for lag in np.arange(0, 40 * ts / N * 8, ts / 40):
        tc = t_first + lag + (np.arange(len(sy)) + 0.5) * ts
        ok = (tc > w['t_score']) & (tc < t[-1] - 1e-9)
        if ok.sum() < 8:
            continue
        vv = np.interp(tc[ok], t, v); e = sy[ok]
        a = float(np.dot(vv, e) / max(np.dot(e, e), 1)); r = float(np.sqrt(np.mean((vv - a * e) ** 2)))
        if best is None or r < best[1]:
            best = (lag, r, a, tc, ok)
    lag, rms, a, tc, ok = best
    sgn = 1 if a >= 0 else -1
    pos = np.zeros(len(sy), int)          # position inside its hold
    for i in range(1, len(sy)):
        pos[i] = pos[i - 1] + 1 if sy[i] == sy[i - 1] else 0
    vc = np.interp(tc, t, v) * sgn
    o = dict(lag_ns=round(lag * 1e9, 2), fit_rms_mv=round(rms * 1e3, 1), polarity=sgn, scored=int(ok.sum()))
    for k, nm in ((1, 'p1'), (-1, 'm1'), (0, 'z')):
        sel = ok & (sy == k) & (pos >= 1)
        if sel.any():
            o[nm] = dict(mean_mv=round(float(np.mean(vc[sel])) * 1e3, 1), min_mv=round(float(np.min(vc[sel])) * 1e3, 1),
                         max_mv=round(float(np.max(vc[sel])) * 1e3, 1), n=int(sel.sum()),
                         pos2_mv=round(float(np.mean(vc[ok & (sy == k) & (pos == 1)])) * 1e3, 1) if (ok & (sy == k) & (pos == 1)).any() else None)
    # longest +-1 hold in the window: first-settled vs last value (droop of the magnetics)
    rr = [r for r in stream.runs(list(sy)) if r[2] != 0 and ok[r[0]] and r[0] + r[1] <= len(sy)]
    if rr:
        s0, ln, lv = max(rr, key=lambda r: r[1])
        o['longest_hold'] = dict(symbols=ln, level=lv, first_mv=round(float(vc[s0 + 1]) * 1e3, 1), last_mv=round(float(vc[s0 + ln - 1]) * 1e3, 1))
    if 'p1' in o and 'm1' in o:
        o['amp_mv'] = round(min(o['p1']['mean_mv'], -o['m1']['mean_mv']), 1)
        o['symmetry'] = round(o['p1']['pos2_mv'] / -o['m1']['pos2_mv'], 4) if o['p1'].get('pos2_mv') and o['m1'].get('pos2_mv') else None
    # leg currents (sink, mA) in the scored window
    di = -(w['ILN'] - w['ILP'])            # pad-side differential current: own lag (no filter delay)
    bd = min(np.arange(-6e-9, 1e-9, 0.1e-9), key=lambda d: -float(np.dot(np.interp(tc[ok] + d, t, di), sy[ok])))
    tc = tc + bd; o['pad_lead_ns'] = round(-bd * 1e9, 2)
    tw0, tw1 = tc[ok][0] - ts / 2, tc[ok][-1] + ts / 2
    s = (t >= tw0) & (t <= tw1)
    for nm in ('ILP', 'ILN'):
        i = -w[nm][s] * 1e3
        o[nm] = dict(peak_ma=round(float(i.max()), 2), avg_ma=round(float(np.trapezoid(i, t[s]) / (t[s][-1] - t[s][0])), 2),
                     **{f'held_{nm2}_ma': round(float(np.mean(np.interp(tc[ok & (sy == k) & (pos >= 1)], t, -w[nm] * 1e3))), 2)
                        for k, nm2 in ((1, 'p1'), (-1, 'm1'), (0, 'z')) if (ok & (sy == k) & (pos >= 1)).any()})
    o['pad_min_v'] = dict(P=round(float(w['PAD_P'][s].min()), 3), N=round(float(w['PAD_N'][s].min()), 3))
    for g in ('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N'):
        if g in w:
            o.setdefault('gate_v', {})[g] = [round(float(np.percentile(w[g][s], q)), 3) for q in (1, 99)]
    for b in ('MAIN_BIAS', 'POST_BIAS'):
        if b in w:
            o.setdefault('bias_v', {})[b] = round(float(np.mean(w[b][s])), 4)
    o['i_vdd_avg_ma'] = round(float(-np.mean(w['I'][s])) * 1e3, 2)
    return o


def run(tag, corner='ss', pess=False, vdd=3.15, code=255, post_code=None, pol=1, pad_model='RT', nsym=26, keep_wave=False):
    post_code = code if post_code is None else post_code
    kw = chain16.setup(dict(pad_model=pad_model)); net = kw['top_ext']; pad_model = kw['pad_model']
    temp = TEMP[corner]; vring = VRING[corner]; res = {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    tn = C13.tune(corner, temp, vring, 0, RATE / 8, pess); f = tn['f_hz']; rate = 8 * f; tw = 40 / rate
    ring = dict(ver='layout', pess=pess, vring=vring, vctrl=tn['vctrl'], band=0, route=tuple(chain16._route))
    sy = stream.mlt3(START + nsym)[START:]
    bits = stream.core_bits(sy, N); nw = len(bits) // 40
    words = [bits[40 * k:40 * k + 40] for k in range(nw)]
    common = dict(corner=corner, temp=temp, vdd=vdd, res=res, pess=pess, ring=ring, rate=rate, codes=[0] * 8, main_code=code, post_code=post_code,
                  en_post=1, pol=pol, idle=0, idle_mode=0, ext=0, dx_bits=None, dx_rate=None, tap=0, mux_ext=None, aux_ext=None,
                  ser_ext=str(C13.FAST / 'wtx_ser8d.ext.spice'), bond='pess', kill=None, S_=1.0,
                  probes=('POST_P', 'POST_N', 'POST_BIAS', 'RJ_P', 'RJ_N'), launch=0.25, supply=None, par=None, top_ext=net, pad_model=pad_model)
    out = dict(tag=tag, bench='full chain', net=str(net), net_sha256=hashlib.sha256(Path(net).read_bytes()).hexdigest(),
               net_label='pt_wiredtx8.fullfix16.rc.spice (s16 snapshot, Magic extresist + fixcap16; pre NAND phase-buffer change)',
               ring='real ring: extracted pt_pll_ring_core layout-11Nov' + (' pess.' if pess else '') + f', open loop vctrl {tn["vctrl"]:.4f}, route 30 ohm/75 fF',
               ring_hz=f, core_rate=rate, n=N, symbol_rate=rate / N, corner=corner, pess=pess, temp=temp, vdd=vdd, vring=vring,
               main_code=code, post_code=post_code, post_pol=pol, pad=C13.PADLABEL[pad_model], board=net100.LABEL,
               stream=dict(source='scrambled idle, x^11+x^9+1, MLT-3', start=START, symbols=[int(x) for x in sy]))
    w1 = RUNS / tag / 'phase'; w1.mkdir(parents=True, exist_ok=True)
    n1 = deck(w1, words=[[0] * 40], word_t0=1.0, tstop=2e-9 + 3 * tw, full=False, **common)
    t0 = time.time(); tools.ngspice_host(w1, 'tb.sp', timeout=40000)
    a = tools.read_wrdata(w1 / 'wave.txt', n1)
    ri = S.crossings(a['time'], a['WORD_CLK40'], th=vdd / 2, rising=True); ri = ri[ri > 2e-9]
    t0w = float(ri[-1]) - (len(ri) - 1) * tw
    for f_ in w1.glob('*'):
        if f_.name != 'tb.sp':
            f_.unlink()
    w2 = RUNS / tag / 'data'; w2.mkdir(parents=True, exist_ok=True)
    names = deck(w2, words=words, word_t0=t0w, tstop=t0w + (nw + 1.5) * tw, full=True, **common)
    tools.ngspice_host(w2, 'tb.sp', timeout=60000)
    out['sec'] = round(time.time() - t0)
    if not (w2 / 'wave.txt').exists():
        out.update(ok=False, reason='no waveform')
    else:
        w = tools.read_wrdata(w2 / 'wave.txt', names); t = w['time']
        up = S.crossings(t, w['TX_RUN'], th=vdd / 2, rising=True)
        out['t_run_ns'] = round(float(up[0]) * 1e9, 1) if len(up) else None
        w['t_score'] = (float(up[0]) if len(up) else 40e-9) + 15e-9      # run detector + filter settling
        out['meas'] = measure(t, w, sy, N / rate, t0w + 0.25 * tw, vdd)
        out['ok'] = True
        np.savez_compressed(RUNS / tag / 'rj.npz', t=t, rj=w['RJ_P'] - w['RJ_N'], ilp=w['ILP'], iln=w['ILN']) if keep_wave else None
    for f_ in w2.glob('*'):
        if f_.name not in ('tb.sp', 'tb.sp.log'):
            f_.unlink()
    RES.mkdir(exist_ok=True); (RES / f'{tag}.json').write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == '__main__':
    o = run(**json.loads(sys.argv[1]))
    print(json.dumps({k: o.get(k) for k in ('tag', 'ok', 'reason', 'sec', 't_run_ns', 'meas')}), flush=True)
