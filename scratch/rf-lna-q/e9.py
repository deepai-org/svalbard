"""E9: which element couples the supply-loop resonance (lossless island decap rows) into the common mode?  usage: e9.py case"""
import sys, re; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
case = sys.argv[1]
def add(lines):
    def p(t):
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i); return t[:e] + lines + '\n' + t[e:]
    return p
P = {'base': None, 'biasgnd': add('Cq1 vtg VSS 1u\nCq2 vtc VSS 1u'), 'vggnd': add('Cq3 vg VSS 1u\nCq4 vcas VSS 1u'),
     'cct10x': add('Cq5 vtk VSS 200p'), 'pbvdd': add('Cq6 pb VDD 1u'), 'allbias': add('Cq1 vtg VSS 1u\nCq2 vtc VSS 1u\nCq3 vg VSS 1u\nCq4 vcas VSS 1u\nCq6 pb VDD 1u')}
W = variant('e9_' + case, patch=P[case])
for kw in (dict(cdec=500e-12), dict(cdec=100e-12)):
    r = LM.stability(W, 'selftest', FF, deg='lowr', **kw); print(case, kw, fmt(r), flush=True)
