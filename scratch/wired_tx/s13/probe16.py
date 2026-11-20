"""Hop set-up / hold and stream-change windows of wtx_ser8d from a ring-driven probe run (runs/p16_*; probe16.sh).
usage: probe16.py <run dir> <vdd> [window lo hi in ns, default -0.1 0.35]
set-up = hop clock rising (vdd/2 at the hop's CK node) - last change of its D before it; hold = next D change - clock.
window: a stream F j must not change in [lo, hi] after the rising edge (1.35 V) of the phase of the slice it feeds
(slice s takes stream (s + 2) mod 8, i.e. F j feeds slice (j - 2) mod 8, phase PH(45 s))."""
import sys, json
sys.path.insert(0, '../s12')
import numpy as np
from chain import S, tools
d, vdd = sys.argv[1], float(sys.argv[2])
lo, hi = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (-0.1, 0.35)
HOPS = {0: (6,), 1: (7,), 2: (0,), 3: (0,), 4: (6, 2), 5: (7, 3), 6: (6, 4), 7: (7, 5)}
CK = {0: 'x0.XH3_0.CK', 2: 'x0.XP2.Q', 3: 'x0.XH5_1.CK', 4: 'x0.XH6_1.CK', 5: 'x0.XH7_1.CK', 6: 'x0.XP6.Q', 7: 'x0.XP7.Q'}
PH = ['PH0', 'PH45', 'PH90', 'PH135', 'PH180', 'PH225', 'PH270', 'PH315']
tb = open(f'{d}/tb.sp').read()
names = [x[2:-1] for x in tb[tb.index('wrdata wave.txt') + 16:].split('\n')[0].split()]
w = tools.read_wrdata(f'{d}/wave.txt', names); t = w['time']
import os
t1 = float(os.environ.get('T1', '60e-9'))
ph0 = S.crossings(t, w['PH0'], th=1.35, rising=True); ph0 = ph0[ph0 > t1]
T = float(np.mean(np.diff(ph0)))
tw = (ph0[0], ph0[-1])
def edges(n, th, rising=None):
    if rising is None:
        e = np.sort(np.concatenate([S.crossings(t, w[n], th=th, rising=True), S.crossings(t, w[n], th=th, rising=False)]))
    else:
        e = S.crossings(t, w[n], th=th, rising=rising)
    return e[(e >= tw[0] - T) & (e <= tw[1] + T)]
out = dict(run=d, ring_period_ps=round(T * 1e12, 1), slot_ps=round(T / 8 * 1e12, 1), hops={}, windows={})
for k, seq in HOPS.items():
    for i, q in enumerate(seq):
        ck = edges(CK[q], vdd / 2, True); ck = ck[(ck > tw[0]) & (ck < tw[1])]
        dd = edges(f'x0.XH{k}_{i}.D', vdd / 2)
        su, ho = [], []
        for c in ck:
            b = dd[dd < c]; a = dd[dd > c]
            if len(b): su.append(c - b[-1])
            if len(a): ho.append(a[0] - c)
        out['hops'][f'XH{k}_{i} (Q{q})'] = dict(setup_min_ps=round(min(su) * 1e12, 1) if su else None, hold_min_ps=round(min(ho) * 1e12, 1) if ho else None)
for j in range(8):
    s_ = (j - 2) % 8
    pe = edges(PH[s_], 1.35, True)
    fe = edges(f'F{j}', vdd / 2)
    rel = []
    for f in fe:
        p = pe[np.argmin(np.abs(pe - f))] if len(pe) else None
        if p is not None:
            r = (f - p) % T
            rel.append(r if r < T / 2 else r - T)
    viol = [round(r * 1e9, 3) for r in rel if lo * 1e-9 <= r <= hi * 1e-9]
    out['windows'][f'F{j} -> slice {s_}'] = dict(changes_ns=sorted(set(round(r * 1e9, 3) for r in rel))[:6], in_window=viol)
out['min_setup_ps'] = min(v['setup_min_ps'] for v in out['hops'].values() if v['setup_min_ps'] is not None)
out['window_violations'] = sum(len(v['in_window']) for v in out['windows'].values())
print(json.dumps(out, indent=1))
