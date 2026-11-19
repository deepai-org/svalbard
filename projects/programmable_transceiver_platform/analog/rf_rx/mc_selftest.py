"""Monte Carlo known-answer test (round 3, coordinator ruling): a matched nfet_03v3 pair, W 10 um / L 1 um, each diode-connected at
20 uA; dVgs = Vgs1 - Vgs2.  Expected sigma (PDK fets_mm: var_vth = 0.7071 par_vth / sqrt(Leff Weff) per device, par_vth = 7.148 mV um,
Leff = L - 0.15 um, Weff = W + 0.1 um; the current-factor term adds < 0.3 mV at this overdrive): sigma(dVgs) = 7.148e-3 / sqrt(0.85 *
10.1) = 2.45 mV.  Pass: measured sigma within 2.45 mV +- 20 % over N runs (declared before the run).  Negative controls (must show
sigma < 0.05 mV): sw_stat_mismatch = 0, and the old M-line rewrite (simlib.ngspice_netlist_mline).
  python3 mc_selftest.py [N]"""
import os, sys, json, statistics
from pathlib import Path
import rfrx_flow as flow, simlib as S
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
W = flow.SCRATCH / 'mc_selftest'; W.mkdir(parents=True, exist_ok=True)
PAIR = """X1 d1 d1 0 0 nfet_03v3 w=10u l=1u
X2 d2 d2 0 0 nfet_03v3 w=10u l=1u
I1 vdd d1 20u
I2 vdd d2 20u
V1 vdd 0 3.3
.control
op
let dv = v(d1) - v(d2)
print dv
.endc
"""
def run(tag, seed, mline=False, mc=True):
    if mc: os.environ['RFRX_MC_SEED'] = str(seed)
    else: os.environ.pop('RFRX_MC_SEED', None)
    body = (S.ngspice_netlist_mline if mline else S.ngspice_netlist)(PAIR)
    log, m = S.run(W, f'{tag}_{seed}.cir', body)
    os.environ.pop('RFRX_MC_SEED', None)
    return m.get('dv')
res = {}
for tag, kw in (('mc', {}), ('neg_nomismatch', dict(mc=False)), ('neg_mline', dict(mline=True))):
    n = N if tag == 'mc' else 10
    v = [run(tag, k + 1, **kw) for k in range(n)]
    v = [x for x in v if x is not None]
    res[tag] = dict(n=len(v), mean_mV=statistics.mean(v) * 1e3, sigma_mV=statistics.pstdev(v) * 1e3)
    print(tag, res[tag], flush=True)
res['expected_sigma_mV'] = 2.45
res['pass'] = bool(abs(res['mc']['sigma_mV'] / 2.45 - 1) <= 0.2 and res['neg_nomismatch']['sigma_mV'] < 0.05 and res['neg_mline']['sigma_mV'] < 0.05)
(flow.GENERATED / 'mc-selftest.json').write_text(json.dumps(res, indent=1)); print('PASS' if res['pass'] else 'FAIL')
for f in W.glob('*'): f.unlink()
