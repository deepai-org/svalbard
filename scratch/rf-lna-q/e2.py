"""E2: which node makes the common-mode input resistance negative?  Ideal interventions on the schematic LNA (ff 32C 3.35V)."""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
def add(lines):
    def p(t):
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
        return t[:e] + lines + '\n' + t[e:]
    return p
cases = {'base': None, 'vcas_gnd': add('Cdx1 vcas VSS 1u'), 'vg_gnd': add('Cdx2 vg VSS 1u'), 'both': add('Cdx1 vcas VSS 1u\nCdx2 vg VSS 1u'),
         'vcas5p': add('Cdx1 vcas VSS 5p'), 'vcas20p': add('Cdx1 vcas VSS 20p')}
for k, p in cases.items():
    W = variant('e2_' + k, patch=p)
    for kw in (dict(), dict(cdec=100e-12, rdec=2.), dict(lsup=0.25e-9), dict(lsup=2e-9)):
        r = LM.stability(W, 'selftest', FF, deg='lowr', **kw); print(k, kw, fmt(r), flush=True)
