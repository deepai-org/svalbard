"""wc_char bench: per-stage delay, TSPC clk->q, setup/hold aperture.  usage: tb.py run CORNER | an CORNER
CORNER in tt ff ss pess (pess = ss/32/3.15 with r7slicer/pess.py applied to the extracted cell)."""
import sys, json, subprocess, shutil
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
W = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'; sys.path.insert(0, W)
import wrx_flow as wf, sims
CORN = dict(tt=('typical', 27, 3.3), ff=('ff', 22, 3.35), ss=('ss', 32, 3.15), pess=('ss', 32, 3.15), ss35=('ss', 32, 3.5),
            sf=('sf', 27, 3.3), fs=('fs', 27, 3.3))
T = 1.6e-9; t0 = 2e-9; N = 200; STEP = 6e-12; OFF0 = -600e-12
def build(cn):
    c, temp, vdd = CORN[cn]
    w = H / cn; w.mkdir(exist_ok=True)
    src = H.parent / 'r7f' / 'fast' / 'wc_char.ext.spice'
    if cn == 'pess':
        subprocess.run(['python3', '/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py', str(src), str(w / 'cell.spice')], check=True)
    else:
        shutil.copy(src, w / 'cell.spice')
    d = [(0, 0.)]; v = 0.
    for n in range(N):
        tn = t0 + n * T + OFF0 + n * STEP
        v = vdd - v
        d += [(tn, vdd - v), (tn + 40e-12, v)]
    pwl = 'PWL(' + ' '.join(f'{a:.6e} {b:.3g}' for a, b in d) + ')'
    L = [f'* char {cn}', sims.sim_header(c, temp), '.option klu', '.include cell.spice',
         f'VDD vdd 0 {vdd}', 'VDDA vdda 0 {}'.format(vdd), 'VSSA vssa 0 0', 'VX0 x0 0 0', 'VX1 x1 0 0', 'VX2 x2 0 0', 'VX3 x3 0 0', 'VENB enb 0 0',
         f'VIN in 0 PULSE(0 {vdd} {t0:.4e} 40p 40p {T / 2 - 40e-12:.4e} {T:.4e})',
         f'VCK ck 0 PULSE(0 {vdd} {t0:.4e} 40p 40p {T / 2 - 40e-12:.4e} {T:.4e})',
         f'VD d 0 {pwl}',
         'X1 in vdda vssa x0 x1 x2 x3 ck d enb ao q ql q2 vdd 0 wc_char', 'CQ q 0 5f', 'CQ2 q2 0 5f', 'CAO ao 0 5f',
         '.control', f'tran 2p {t0 + N * T:.4e} 0 2p', 'set wr_singlescale',
         'wrdata out.txt v(in) ' + ' '.join(f'v(x1.n{i})' for i in range(6)) + ' v(x1.nd2) v(ao) v(ck) v(x1.ckl) v(d) v(q) v(q2) v(ql)', '.endc', '.end']
    (w / 'tb.cir').write_text('\n'.join(L) + '\n')
    return w
def cross(t, x, th, rising=None):
    v = x > th; i = np.where(v[1:] != v[:-1])[0]
    if rising is not None: i = i[v[i + 1] == rising]
    return t[i] + (th - x[i]) * (t[i + 1] - t[i]) / (x[i + 1] - x[i])
def an(cn):
    c, temp, vdd = CORN[cn]; w = H / cn
    d = np.loadtxt(w / 'out.txt'); t = d[:, 0]
    cols = ['in'] + [f'n{i}' for i in range(6)] + ['nd2', 'ao', 'ck', 'ckl', 'd', 'q', 'q2', 'ql']
    X = {n: d[:, k + 1] for k, n in enumerate(cols)}
    th = vdd / 2
    def dl(a, b):
        ea = cross(t, X[a], th); eb = cross(t, X[b], th); out = []
        for x in ea[ea > t0 + 2 * T]:
            j = np.searchsorted(eb, x)
            if j < len(eb): out.append(eb[j] - x)
        return float(np.median(out)) if out else None
    stage = (dl('n0', 'n5')) / 5
    R = dict(corner=cn, inv_stage_ps=round(stage * 1e12, 1), nand2x2_ps=round(dl('n5', 'nd2') * 1e12, 1), aoi3_ps=round(dl('nd2', 'ao') * 1e12, 1),
             ck_to_ckl_ps=round(dl('ck', 'ckl') * 1e12, 1))
    ckl = cross(t, X['ckl'], th, True); ckl = ckl[ckl > t0]
    dtr = cross(t, X['d'], th)
    rows = []
    for n in range(2, N - 1):
        e = ckl[n] if n < len(ckl) else None
        if e is None: break
        off = dtr[np.argmin(abs(dtr - e))] - e      # nearest D transition, relative to the flop clock
        k = np.searchsorted(t, ckl[n + 1] - 30e-12) if n + 1 < len(ckl) else len(t) - 1
        qv = X['q'][k] > th
        dk = np.searchsorted(t, e + 0.45 * T); dnew = X['d'][np.searchsorted(t, e + off + 60e-12)] > th if off < 0 else X['d'][dk] > th
        dold = X['d'][np.searchsorted(t, e - 0.45 * T)] > th
        qe = cross(t[(t > e) & (t < e + 0.9 * T)], X['q'][(t > e) & (t < e + 0.9 * T)], th)
        rows.append(dict(off_ps=round(off * 1e12, 1), q=int(qv), dval_after=int(X['d'][np.searchsorted(t, e + 0.4 * T)] > th), dval_before=int(dold),
                         clkq_ps=round((qe[0] - e) * 1e12, 1) if len(qe) else None))
    # nominal clk->q: offsets far from the edge where Q changed
    cq = [r['clkq_ps'] for r in rows if r['clkq_ps'] and abs(r['off_ps']) > 300]
    nom = float(np.median(cq)) if cq else None
    # setup: most negative offset (D before edge) region must give Q = value after the D edge; find smallest |off| with correct new value and clkq <= 1.1 nom
    su = [r for r in rows if -500 < r['off_ps'] < 0]; ho = [r for r in rows if 0 < r['off_ps'] < 500]
    ok_su = [r for r in su if r['q'] == r['dval_after'] and (r['clkq_ps'] is None or r['clkq_ps'] <= 1.1 * nom)]
    bad_su = [r for r in su if not (r['q'] == r['dval_after'] and (r['clkq_ps'] is None or r['clkq_ps'] <= 1.1 * nom))]
    ok_ho = [r for r in ho if r['q'] == r['dval_before'] and (r['clkq_ps'] is None or r['clkq_ps'] <= 1.1 * nom)]
    bad_ho = [r for r in ho if not (r['q'] == r['dval_before'] and (r['clkq_ps'] is None or r['clkq_ps'] <= 1.1 * nom))]
    R.update(clkq_ckl_ps=nom, ck_pin_to_q_ps=round(nom + R['ck_to_ckl_ps'], 1) if nom else None,
             t_setup_ps=round(-min(r['off_ps'] for r in bad_su), 1) if bad_su else 0.0,
             t_hold_ps=round(max(r['off_ps'] for r in bad_ho), 1) if bad_ho else 0.0,
             n_su=len(su), n_ho=len(ho))
    (w / 'char.json').write_text(json.dumps(dict(R, rows=rows), indent=1)); print(json.dumps(R))
if __name__ == '__main__':
    if sys.argv[1] == 'run':
        w = build(sys.argv[2]); wf.ngspice(w, 'tb.cir', timeout=3600); an(sys.argv[2])
    else:
        an(sys.argv[2])
