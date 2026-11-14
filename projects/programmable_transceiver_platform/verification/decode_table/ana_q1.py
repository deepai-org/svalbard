import random, collections
from gen import *; import model
# regenerate the same vectors (same seed, same order) without running
src = open('run_q1.py').read().split("write_tb(")[0]
exec(src)
R = read_out(); bad = collections.Counter(); ex = {}; nf = 0
for (F, D, B), O in zip(V, R):
    if any(F[k] for k in F if k.startswith('monitor.config.require')): nf += 1; continue
    Oi = {k: (int(v, 16) if 'x' not in v and 'z' not in v else None) for k, v in O.items()}
    E = model.expect(F, D, Oi)
    for n, w, _ in PORTS:
        if n in model.DYNAMIC or E.get(n) is None: continue
        if Oi[n] != E[n]:
            bad[n] += 1; ex.setdefault(n, []).append((E[n], O[n], F, D))
print(len(V) - nf, 'vectors compared;', 'mismatching ports:', len(bad))
for n, k in bad.most_common():
    e, o, F, D = ex[n][0]; print(f'  {n}: {k} vectors, e.g. expected {e:x} got {o}')
import pickle; pickle.dump({n: [(e, o, {k: v for k, v in F.items()}, D) for e, o, F, D in ex[n][:5]] for n in ex}, open('bad.pkl', 'wb'))
