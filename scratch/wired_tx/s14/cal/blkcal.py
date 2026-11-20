"""Block-level slot-width calibration of the phase trim of pt_wiredtx8 (extends ../../s13/cal.py to the block top).

Method (cal.py's, through the real data path): the 40 D inputs of wtx_ser8d get static words in which only stream j is 1
(stream j = D(j + 8 i), i = 0..4), so the mux output is high for exactly one slot per ring cycle: the slot of the slice
that carries stream j.  In the block slice s takes stream (s + FROT) mod 8 (wtx8_top.FROT = 2), so stream j lights slot
s = (j - FROT) mod 8 = [rise PH s, rise PH s+1).  D_s = DC average of MAIN_N - MAIN_P over whole ring cycles (on chip:
ATB_AVGP / ATB_AVGN, 100 kohm + ATB capacitance; here numerically over the same span).  All D_s equal <=> all slots
equal (null method).  Width error e_s = (D_s - mean D) / G, G = (D(all ones) - D(all zeros)) / T_ring.  Edge s position
p_s = sum_{r<s} e_r (p_0 = 0); TR k delays edge k (rise of PH k at slice k), so new code_k = code_k + round((max p - p_k)
/ LSB), shifted to min 0, clipped to 15.
One transient per measurement: LEAD all-zero words (ring + run detector start-up; D(all zeros) is read at its end),
then 8 one-hot segments and one all-ones segment of NSEG words each, then TAIL zero words.  The pipeline latency is
found in the run itself (first zero crossing of MAIN_N - MAIN_P after the first one-hot launch); each segment is read
over whole ring cycles inside [launch + latency + MARGIN, launch + latency + NSEG words - MARGIN].
Independent check from probes: rising edges of PH k at the mux input and falling edges of the slice node XMUX.XS k.X
(start of slot k) give the slot widths directly in time (`probe_slot_ps`).

    python3 blkcal.py '{"tag":"bc_ssp","corner":"ss","pess":true,"vdd":3.15,"codes":[0,1,3,3,4,5,3,7],"top_ext":"..."}'
"""
import sys, json, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'chain'))
import chain14
from chain14 import C13, tools
from chain13 import S, CH

FROT = 2
LEADW, NSEG, TAILW = 5, 2, 2
MARGIN = 0.3            # words
LSB = dict(ssp=14.4, ss=13.0, tt=10.5, typical=10.5, ff=8.3)


def words_for():
    z = [0] * 40
    W = [z] * LEADW
    for j in range(8):
        W += [[1 if i % 8 == j else 0 for i in range(40)]] * NSEG
    W += [[1] * 40] * NSEG + [z] * TAILW
    return W


def measure(tag, corner='ss', temp=32, vdd=3.15, vring=2.69, pess=False, rate=3.125e9, codes=None, top_ext=None, pad_model='C',
            ring_ver='layout', keep=False):
    codes = codes or [0] * 8
    xs = (lambda k: f'XTOP.XMUX.XS{k}.X') if 'full' in str(top_ext) else (lambda k: f'XTOP.XMUX__XS{k}__X')
    f = rate / 8
    band = 1 if f > 480e6 else 0
    tn = C13.tune(corner, temp, vring, band, f, pess)
    f = tn['f_hz']; rate = 8 * f; tw = 40 / rate
    ring = dict(ver=ring_ver, pess=pess, vring=vring, vctrl=tn['vctrl'], band=band)
    common = dict(corner=corner, temp=temp, vdd=vdd, res={'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical'), pess=pess, ring=ring, rate=rate,
                  codes=codes, main_code=160, post_code=0, en_post=0, pol=0, idle=0, idle_mode=0, ext=0, dx_bits=None, dx_rate=None, tap=0,
                  mux_ext=None, aux_ext=None, ser_ext=str(C13.FAST / 'wtx_ser8d.ext.spice'), bond='pess', kill=None, S_=1.0,
                  probes=[f'PH{k}' for k in range(1, 8)] + [xs(k) for k in range(8)], launch=0.25, supply=None, par=None,
                  top_ext=top_ext, pad_model=pad_model)
    root = C13.RUNS / tag
    w1 = root / 'phase'; w1.mkdir(parents=True, exist_ok=True)
    n1 = C13.deck(w1, words=[[0] * 40], word_t0=1.0, tstop=2e-9 + 3 * tw, full=False, **common)
    tools.ngspice_host(w1, 'tb.sp', timeout=40000)
    a = tools.read_wrdata(w1 / 'wave.txt', n1)
    ri = S.crossings(a['time'], a['WORD_CLK40'], th=vdd / 2, rising=True); ri = ri[ri > 2e-9]
    t0w = float(ri[-1]) - (len(ri) - 1) * tw
    W = words_for()
    w2 = root / 'data'; w2.mkdir(parents=True, exist_ok=True)
    names = C13.deck(w2, words=W, word_t0=t0w, tstop=t0w + (len(W) + 1) * tw, full=True, **common)
    t_sim = time.time(); tools.ngspice_host(w2, 'tb.sp', timeout=80000); t_sim = time.time() - t_sim
    w = tools.read_wrdata(w2 / 'wave.txt', names); t = w['time']
    d = w['MAIN_N'] - w['MAIN_P']
    e0 = S.crossings(t, w['PH0'], th=vring / 2, rising=True)
    T = float(np.median(np.diff(e0[len(e0) // 3:])))
    launch = lambda k: t0w + k * tw + 0.25 * tw
    seg0 = launch(LEADW)
    up = S.crossings(t, d, th=0.0, rising=True); up = up[up > seg0]
    lat = float(up[0]) - seg0

    def avg(ta, tb):
        cyc = e0[(e0 >= ta) & (e0 <= tb)]
        m = (t >= cyc[0]) & (t <= cyc[-1])
        return float(np.trapezoid(d[m], t[m]) / (cyc[-1] - cyc[0])), len(cyc) - 1
    D0, n0 = avg(seg0 + lat - 2 * tw + MARGIN * tw, seg0 + lat - MARGIN * tw)
    Dj, nc = [], []
    for j in range(9):
        a0 = seg0 + j * NSEG * tw + lat
        v, n = avg(a0 + MARGIN * tw, a0 + NSEG * tw - MARGIN * tw); Dj.append(v); nc.append(n)
    # probe check: slot s starts at the fall of XMUX.XS s.X (follows rise of PH s); widths over the lead (all-zero) part
    pr = {}
    try:
        st = []
        for k in range(8):
            x = w[xs(k)]
            st.append(S.crossings(t, x, th=vdd / 2, rising=False))
        ref = st[0][(st[0] > seg0 - 2 * tw) & (st[0] < seg0 + 8 * tw)]
        pos = []
        for k in range(8):
            pos.append(float(np.mean([st[k][st[k] >= r][0] - r for r in ref[:-1]])))
        pos = np.array(pos); wid = np.diff(np.concatenate([pos, [T]]))
        pr = dict(probe_edge_ps=[round(x * 1e12, 1) for x in pos], probe_slot_err_ps=[round((x - T / 8) * 1e12, 1) for x in wid])
        phe = []
        for k in range(8):
            ek = S.crossings(t, w[f'PH{k}'], th=vring / 2, rising=True)
            phe.append(float(np.mean([ek[ek >= r - 0.3 * T][0] - r for r in ref[:-1]])))
        pr['ph_edge_ps_rel_x0'] = [round(x * 1e12, 1) for x in phe]
    except Exception as ex:      # noqa
        pr = dict(probe_error=str(ex)[:200])
    if not keep:
        for f_ in list(w1.glob('*')) + list(w2.glob('*')):
            if f_.name not in ('tb.sp',):
                f_.unlink(missing_ok=True)
    return dict(D=Dj, D0=D0, T=T, f_mhz=1e-6 / T, latency_ns=lat * 1e9, cycles=nc, n0=n0, sim_s=round(t_sim), **pr)


def step(m, codes, lsb_ps):
    Dstream = np.array(m['D'][:8]); G = (m['D'][8] - m['D0']) / m['T']
    Dslot = np.array([Dstream[(s + FROT) % 8] for s in range(8)])
    e = (Dslot - Dslot.mean()) / G
    G2 = (Dslot.sum() - 8 * m['D0']) / m['T']                 # gain from the one-hot sum (cross-check)
    p = np.concatenate([[0.0], np.cumsum(e)[:-1]])
    corr = p.max() - p
    new = np.array(codes) + np.round(corr / (lsb_ps * 1e-12)).astype(int)
    new -= new.min()
    return dict(slot_err_ps=[round(x * 1e12, 1) for x in e], edge_ps=[round(x * 1e12, 1) for x in p],
                slot_err_ps_G2=[round(x * 1e12, 1) for x in (Dslot - Dslot.mean()) / G2], gain_ratio=round(G2 / G, 3),
                codes=[int(min(15, x)) for x in new], worst_slot_ps=round(float(np.max(np.abs(e))) * 1e12, 1))


def run(tag, corner='ss', pess=False, codes=None, lsb=None, ilk_bypass=False, **kw):
    chain14._bypass = bool(ilk_bypass)
    codes = codes or [0] * 8
    key = 'ssp' if (corner == 'ss' and pess) else corner
    lsb = lsb or LSB[key]
    m = measure(tag, corner=corner, pess=pess, codes=codes, **kw)
    s = step(m, codes, lsb)
    top = kw.get('top_ext')
    out = dict(tag=tag, corner=corner, pess=pess, ring='ring=layout-11Nov' + (' pess' if pess else ''), padm=C13.PADLABEL[kw.get('pad_model', 'C')],
               net_sha256=chain14.sha(top), top_ext=top, codes_in=codes, lsb_ps=lsb, meas=m, **s,
               residual_ok=bool(s['worst_slot_ps'] <= 8.0), ilk_bypass=bool(ilk_bypass))
    (HERE / 'res').mkdir(exist_ok=True)
    (HERE / 'res' / f'{tag}.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(tag=tag, codes_in=codes, slot_err_ps=s['slot_err_ps'], worst=s['worst_slot_ps'], next_codes=s['codes'],
                          probe=m.get('probe_slot_err_ps'), gain_ratio=s['gain_ratio'], lat_ns=round(m['latency_ns'], 2), sim_s=m['sim_s'])), flush=True)
    return out


if __name__ == '__main__':
    run(**json.loads(sys.argv[1]))
