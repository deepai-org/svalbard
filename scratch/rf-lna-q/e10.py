"""E10: supply-network cases on the schematic LNA (ff 32C 3.35V, lowr): damped island decap and the real PDN.  usage: e10.py idx"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
W = variant('e10', like='extpr')
G = {'a': [dict(cdec=100e-12, rdec=r) for r in (0.5, 1., 2., 4.)],
     'b': [dict(cdec=500e-12, rdec=r) for r in (0.25, 0.5, 1., 2.)],
     'c': [dict(cdie=5.4e-9, rdie=0.1, rsw=0.3, lsup=l) for l in (0.25e-9, 0.5e-9, 1e-9)] + [dict(cdie=5.4e-9, rdie=0.03, rsw=0.2, lsup=0.5e-9), dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=1e-9)],
     'd': [dict(cdec=100e-12, rsw=0.25), dict(cdec=500e-12, rsw=0.25), dict(cdec=100e-12, rsw=0.25, cdie=5.4e-9, rdie=0.05, lsup=0.5e-9), dict(cdec=500e-12, rsw=0.25, cdie=5.4e-9, rdie=0.05, lsup=0.5e-9)]}
for kw in G[sys.argv[1]]:
    r = LM.stability(W, 'selftest', FF, deg='lowr', **kw); print(kw, fmt(r).replace('mu 1.0000 ', ''), flush=True)
