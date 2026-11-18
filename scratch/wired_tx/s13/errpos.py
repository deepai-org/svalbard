"""which bits fail: position mod 8 / mod 40 of the errors at gate / far for an s12 chain run."""
import sys, json
sys.path.insert(0, '../s12')
import numpy as np
import chain as C
from chain import S, tools
tag = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else '../s12'
r = json.load(open(f'{base}/results/{tag}.json'))
names = ['time', 'PH0', 'WCKQ', 'i(VDD)', 'MAIN_P', 'MAIN_N', 'PAD_P', 'PAD_N', 'FAR_P', 'FAR_N']
w = tools.read_wrdata(f'{base}/runs/{tag}/{tag}_data/wave.txt', names[1:])
t = w['time']; vdd = r['vdd']
ed = C.wck_grid(t, w['WCKQ'], vdd / 2, 3e-9)
nw = 9; ub = np.array(S.prbs7_bits(40 * nw))
for nm, a, b in (('gate', 'MAIN_P', 'MAIN_N'), ('far', 'FAR_P', 'FAR_N')):
    sc = r[nm]; v = w[a] - w[b]
    e = ed[2:-1][:nw - 4 + 1]
    sel = (t > e[0]) & (t < e[-1]); v = v - 0.5 * (np.percentile(v[sel], 99) + np.percentile(v[sel], 1))
    basep = np.concatenate([e[m] + np.arange(40) / 40 * (e[m + 1] - e[m]) for m in range(len(e) - 1)])
    ui = np.mean(np.diff(e)) / 40
    best = None
    for phi in np.arange(0, 1, 1 / 32):
        vs = np.interp(basep + phi * ui, t, v); bits = (vs > 0).astype(int)
        if sc['inverted']: bits = 1 - bits
        ref = ub[sc['latency']:sc['latency'] + len(bits)]
        bad = np.nonzero(bits != ref)[0]
        if best is None or len(bad) < len(best[1]): best = (phi, bad, ref)
    phi, bad, ref = best
    idx = (bad + sc['latency'])
    print(nm, 'phi', phi, 'errors', len(bad), 'word-bit mod 8:', np.bincount(idx % 8, minlength=8), 'mod 40:', sorted(set(idx % 40)))
    print('  expected value at errors:', ref[bad])
