import json, sys, numpy as np, plan_lib as P
U = np.load(sys.argv[1]); G = float(sys.argv[2]); cuts = json.load(open(sys.argv[3])); E = json.load(open(sys.argv[4]))
t = P.cut_table(U, {k: tuple(v) for k, v in cuts.items()}, G)
for k, v in t.items(): print(f'{k:34s} demand {v[0]:5d}  capacity {v[1]:6d}  util {v[2]:.2f}')
cu = P.chan_util(U, E['channels'], G)
for k, v in cu.items(): print(f'chan {k:20s} {v}')
uH, uV, cH, cV = U
free = (cV > 0.5 * G / 0.56)    # gcells at least half free (real channel, not a sliver)
rv = np.where(free, uV / np.maximum(cV, 1e-3), 0); rh = np.where(cH > 0.5 * G / 0.56, uH / np.maximum(cH, 1e-3), 0)
print('channel gcells (>=50% free): V >70%', int((rv > 0.7).sum()), '>100%', int((rv > 1).sum()), '| H >70%', int((rh > 0.7).sum()), '>100%', int((rh > 1).sum()), '| of', int(free.sum()))
