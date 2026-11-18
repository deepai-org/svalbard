"""Slot-width calibration of the phase trim from DC observables only (what the chip offers: AVG_P / AVG_N on the ATB).

Method: the digital sends the static word in which only stream j is 1 (40-bit word = 5 x the 8-bit one-hot pattern).
The mux output is then high for exactly one slot per ring cycle, the slot of the slice that carries stream j, and the
DC average D_s = mean(MAIN_N - MAIN_P) measures that slot's width.  All eight D_s equal <=> all slots equal (a null
method: gain, offset and edge shape are common to the eight measurements).  width error e_s = (D_s - mean D) / G with
G = dD/dwidth = (D(all ones) - D(all zeros)) / T_ring, both also DC readings.  Slot s runs from edge s to edge s + 1, so
the edge positions follow by cumulative sum and the trim codes are the rounded corrections (min code 0).
In simulation the average is taken numerically over whole ring cycles (the 100 kohm AVG resistors + ATB capacitance do
the same on the chip).  One transient holds all ten patterns.

    python3 cal.py '{"tag":"cal_ss","c":"ss","ring":{"vring":2.69,"vctrl":1.3241},"iters":2}'
"""
import sys, json
import numpy as np
import m9
from chain import S

NCYC = 6            # ring cycles per pattern (the first two are discarded)
LEAD = 10           # ring cycles of all-zero pattern first (the real ring is still settling: measured, slot 0 read 38 ps short without it)
LSB_GUESS = dict(ss=13.0, ssp=14.4, ssT=12.0, sspT=13.0, tt=10.5, ff=8.3, sf=11.0, fs=11.0)


def measure(tag, c, ring, codes, **kw):
    pats = [[1 if i == j else 0 for i in range(8)] for j in range(8)] + [[1] * 8, [0] * 8]
    fpat = [(LEAD, [0] * 8)] + [(NCYC, p) for p in pats]
    f_guess = kw.pop('f', 390.6e6)
    r = m9.run(tag, c=c, rate=8 * f_guess, fpat=fpat, ring=ring, codes=codes, probes=[f'PH{k}' for k in range(1, 8)], **kw)
    o, w = r; t = w['time']
    sw = ring['vring'] if ring else m9.CORN[c]['swing']
    e0 = S.crossings(t, w['PH0'], th=sw / 2, rising=True)
    T = float(np.median(np.diff(e0[3:])))
    ui = 1 / (8 * f_guess)
    d = w['MAIN_N'] - w['MAIN_P']; D = []
    for j in range(10):
        ts = 1e-9 + (LEAD + j * NCYC) * 8 * ui                      # segment start in bench time (bench assumes f_guess)
        cyc = e0[(e0 > ts + 2.2 * 8 * ui) & (e0 < ts + NCYC * 8 * ui - 0.2 * 8 * ui)]
        m = (t >= cyc[0]) & (t <= cyc[-1])
        D.append(float(np.trapezoid(d[m], t[m]) / (cyc[-1] - cyc[0])))
    return dict(D=D, T=T, f_mhz=1e-6 / T, i_ma=o['i_ma'])


def step(meas, codes, lsb_ps, frot=0):
    D = np.array(meas['D'][:8]); G = (meas['D'][8] - meas['D'][9]) / meas['T']          # V per second of width
    e = (D - D.mean()) / G                                                              # width error of the slot carrying stream j
    # in the bench stream j sits in slice j; slot s = [edge s, edge s+1): edge positions p_s, p_0 = 0
    p = np.concatenate([[0.0], np.cumsum(e)[:-1]])
    corr = -(p - p.max())                                                               # delay to add to each edge (>= 0)
    new = np.array(codes) + np.round(corr / (lsb_ps * 1e-12)).astype(int)
    new -= new.min()
    return dict(slot_err_ps=[round(x * 1e12, 1) for x in e], edge_ps=[round(x * 1e12, 1) for x in p], codes=[int(min(15, x)) for x in new])


def run(tag, c='ss', ring=None, iters=2, codes=None, lsb=None, **kw):
    codes = codes or [0] * 8; hist = []
    lsb = lsb or LSB_GUESS[c]
    for it in range(iters + 1):
        m = measure(f'{tag}_i{it}', c, ring, codes, **kw)
        s = step(m, codes, lsb)
        hist.append(dict(iter=it, codes=codes, f_mhz=round(m['f_mhz'], 2), slot_err_ps=s['slot_err_ps'],
                         span_ps=round(max(s['edge_ps']) - min(s['edge_ps']), 1), worst_slot_ps=max(abs(x) for x in s['slot_err_ps'])))
        print(json.dumps(hist[-1]), flush=True)
        (m9.RUNS / f'{tag}_i{it}' / 'wave.txt').unlink(missing_ok=True)
        if it < iters:
            codes = s['codes']
    out = dict(tag=tag, c=c, ring=ring, lsb_guess_ps=lsb, history=hist, final_codes=hist[-1]['codes'])
    (m9.HERE / 'calres').mkdir(exist_ok=True); (m9.HERE / 'calres' / f'{tag}.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    run(**json.loads(sys.argv[1]))
