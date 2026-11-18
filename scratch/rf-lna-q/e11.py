import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import numpy as np
tag = sys.argv[1]; mods = {k: eval(v) for k, v in (x.split('=', 1) for x in sys.argv[2:])}
W = variant('e11_' + tag, mods=mods)
r = LM.stability(W, 'selftest', FF, deg='lowr'); print(tag, fmt(r))
f = sorted(W.glob('stab_selftest_*_cm0_zr.txt'))[-1]; d = np.array(S.read_table(f)); F = d[:, 0] / 1e9
print(tag, 'cm', ' '.join('%g:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (0.2, 0.5, 1, 1.5, 2, 2.4, 3, 4, 6, 8, 10, 13, 16, 20, 30)))
