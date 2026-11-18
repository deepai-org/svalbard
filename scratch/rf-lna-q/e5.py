"""E5: Re(Zcm) curve (not only the minimum) for one variant/supply case; prints Re at selected frequencies.
usage: e5.py ct rt ccm rcm rfd cct  key=val ... (lsup= cdec= rdec= att=)"""
import sys, re, os; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import numpy as np
pos = [x for x in sys.argv[1:] if '=' not in x]; kw = {k: float(v) for k, v in (x.split('=') for x in sys.argv[1:] if '=' in x)}
sys.argv = [sys.argv[0]] + pos
os.environ['CASES'] = 'none'
src = open(Q / 'e4.py').read().split("full = os.environ")[0]
exec(src)
if 'att' in kw: kw['att'] = int(kw['att'])
r = LM.stability(W, 'selftest', corner, deg='lowr', **kw); print(tag, kw, fmt(r))
for lo in (0, 1):
    f = sorted(W.glob('stab_selftest_*_cm%d_zr.txt' % lo), key=lambda p: p.stat().st_mtime)[-1]; print(f.name)
    d = np.array(S.read_table(f)); F = d[:, 0] / 1e9
    print('lo', lo, ' '.join('%.2fG:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (0.1, 0.16, 0.2, 0.3, 0.5, 0.8, 1.2, 1.8, 2.4, 3.5, 5, 8, 12, 16, 22, 30)))
