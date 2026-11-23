"""Phase noise of QVCO r9 in its real environment (envq deck: extracted rft9f RF cell, core-top C topc9g, spiral 290 um
model, r17 loads), method of lcvco/run_qvco_r5_ext.pnoise (fork A): white tank-loss current noise injected at each tank
node, i_n^2 = 4kT (1+gamma) 2/Rp with Rp = Q * 2 pi f0 L (gamma 2), zero-crossing phase of DI -> Welch -> L(f).
Device noise models and flicker up-conversion are NOT included (same limitation as the r5 record).
usage: pn9.py <corner> <band> <vtune> [T]   (env as q12.sh: QRFW, QTOPC, SPIRAL_SPICE)"""
import sys, json, math
from pathlib import Path
import numpy as np
from scipy.signal import welch
sys.argv_saved = list(sys.argv)
import envq as E
cname, code, vt = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
T = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5e-6
L = {'pt_spiral': 2.475e-9, 'pt_spiral_l115_q4': 2.846e-9, 'pt_spiral_l85_q4': 2.104e-9}
Q = {'pt_spiral': 8.4, 'pt_spiral_l115_q4': 4.0, 'pt_spiral_l85_q4': 4.0}
c = E.rx.CORNERS[cname]
lval, q = L.get(c['spiral'], 2.475e-9), Q.get(c['spiral'], 8.4)
k, Tk, f0, nt = 1.380649e-23, 300.15, 2.45e9, 2e-12
s_i = 4 * k * Tk * (2 / (q * 2 * math.pi * f0 * lval)) * 3.0
sigma = math.sqrt(s_i / (2 * nt)) * float(__import__('os').environ.get('PN_SCALE', '1'))   # PN_SCALE=0: negative control (deterministic floor)
tag = f'pn_{cname}_{code}_{vt}' + ('_s' + __import__('os').environ['PN_SCALE'] if __import__('os').environ.get('PN_SCALE') else '')
wd = E.HERE / 'rpn' / tag
wd.mkdir(parents=True, exist_ok=True)
E.rx.SIM = E.HERE / 'proc'
d, hashes = E.deck(cname, code, vt, 'r17', wd=wd, route=20.0, T=T)
d = d[:d.index('.tran')] + ''.join(f'INZ{n} {n} 0 dc 0 trnoise({sigma:.4e} {nt:.3e} 0 0)\n' for n in ('ip', 'in', 'qp', 'qn')) + f""".save v(di)
.control
tran 1p {T} 0 2p
wrdata di.txt v(di)
quit
.endc
.end
"""
E.tf.ngspice(wd, 'pn', d, timeout=200000)
data = np.loadtxt(wd / 'di.txt'); tt, x = data[:, 0], data[:, 1]
s = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
tc = tt[s] - x[s] * (tt[s + 1] - tt[s]) / (x[s + 1] - x[s]); tc = tc[tc > 0.08e-6]
n = np.arange(len(tc)); p = np.polyfit(n, tc, 1); fosc = 1 / p[0]
phi = 2 * math.pi * fosc * (tc - np.polyval(p, n))
rec = dict(sigma_a=sigma, case=tag, f_osc_hz=fosc, cycles=len(tc), t_sim_s=T, tank_q=q, l_h=lval, injected_a2_hz=s_i, hashes=hashes)
fr, sphi = welch(phi - phi.mean(), fs=fosc, nperseg=256, detrend='linear'); lf = sphi / 2
sel = (fr > 4e6) & (fr < 80e6)
rec['L_1MHz_from_1f2_fit_4_80MHz'] = float(10 * np.log10(np.mean(lf[sel] * (fr[sel] / 1e6) ** 2)))
rec['L_3MHz_from_fit'] = rec['L_1MHz_from_1f2_fit_4_80MHz'] - 20 * math.log10(3)
rec['L_40MHz_from_fit'] = rec['L_1MHz_from_1f2_fit_4_80MHz'] - 20 * math.log10(40)
rec['method'] = 'transient + injected white tank-loss current noise (fork A), no device noise models, no flicker'
(wd / 'result.json').write_text(json.dumps(rec, indent=1)); print(json.dumps(rec)); (wd / 'di.txt').unlink()
