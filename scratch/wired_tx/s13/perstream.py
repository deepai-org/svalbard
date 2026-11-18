"""per-slot latency: for each line-bit position mod 8, the shift (in ring cycles) that best matches PRBS."""
import sys, json
sys.path.insert(0, '../s12')
import numpy as np
import chain as C
from chain import S, tools
tag = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else '../s12'; nw = int(sys.argv[3]) if len(sys.argv) > 3 else 9
r = json.load(open(f'{base}/results/{tag}.json'))
tb = open(f'{base}/runs/{tag}/{tag}_data/tb.sp').read()
names = [x[2:-1] if x.startswith('v(') else x for x in tb[tb.index('wrdata wave.txt') + 16:].split('\n')[0].split()]
w = tools.read_wrdata(f'{base}/runs/{tag}/{tag}_data/wave.txt', names)
t = w['time']; vdd = r['vdd']
ed = C.wck_grid(t, w['WCKQ'], vdd / 2, 3e-9)
ub = np.array(S.prbs7_bits(40 * nw))
sc = r['gate']; v = w['MAIN_P'] - w['MAIN_N']
e = ed[2:-1][:nw - 4 + 1]
sel = (t > e[0]) & (t < e[-1]); v = v - 0.5 * (np.percentile(v[sel], 99) + np.percentile(v[sel], 1))
basep = np.concatenate([e[m] + np.arange(40) / 40 * (e[m + 1] - e[m]) for m in range(len(e) - 1)])
ui = np.mean(np.diff(e)) / 40
for phi in (float(sys.argv[4]),) if len(sys.argv) > 4 else (0.1, 0.35, 0.6, 0.85):
    vs = np.interp(basep + phi * ui, t, v); bits = (vs > 0).astype(int)
    if sc['inverted']: bits = 1 - bits
    lat = sc['latency']; out = []
    for s in range(8):
        pos = np.arange(len(bits)); m = (pos + lat) % 8 == s
        res = {}
        for sh in (-16, -8, 0, 8, 16):
            idx = pos[m] + lat + sh
            ok = (idx >= 0) & (idx < len(ub))
            res[sh] = int(np.sum(bits[m][ok] != ub[idx[ok]]))
        out.append((s, res, round(float(np.min(np.abs(vs[m]))), 2)))
    print('phi', phi)
    for o in out: print('   slot', o)
