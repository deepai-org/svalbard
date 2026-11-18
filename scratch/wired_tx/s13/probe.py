"""edge timing of the probed wtx_ser8d nodes, relative to PH0 rising, over a few ring cycles."""
import sys
sys.path.insert(0, '../s12')
import numpy as np
from chain import S, tools
d = sys.argv[1]; vdd = float(sys.argv[2]); t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 60e-9; ncyc = int(sys.argv[4]) if len(sys.argv) > 4 else 3
tb = open(f'{d}/tb.sp').read()
names = [x[2:-1] for x in tb[tb.index('wrdata wave.txt') + 16:].split('\n')[0].split()]
names = ['I' if n.lower() == 'vdd' else n for n in names]
w = tools.read_wrdata(f'{d}/wave.txt', names); t = w['time']
ph0 = S.crossings(t, w['PH0'], th=1.35, rising=True); ph0 = ph0[ph0 > t1][:ncyc + 1]
T = np.mean(np.diff(ph0)); print('ring period ps', round(T * 1e12, 1), 'slot', round(T / 8 * 1e12, 1))
def ev(n, th=vdd / 2):
    v = w[n]; out = []
    for r in (True, False):
        for x in S.crossings(t, v, th=th, rising=r):
            if ph0[0] <= x < ph0[-1]:
                k = np.searchsorted(ph0, x) - 1
                out.append((k, round((x - ph0[k]) / (T / 8), 2), 'r' if r else 'f'))
    return sorted(out)
for n in names:
    if n in ('I', 'WCKQ') or n.startswith(('MAIN', 'PAD', 'FAR')): continue
    th = 1.35 if n.startswith('PH') else vdd / 2
    e = ev(n, th)
    print(f'{n:14s} max {w[n][(t>ph0[0])&(t<ph0[-1])].max():.2f} min {w[n][(t>ph0[0])&(t<ph0[-1])].min():.2f} ', ' '.join(f'{k}:{s}{x}' for k, x, s in e))
