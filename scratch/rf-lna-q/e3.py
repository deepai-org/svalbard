"""E3: local return of the load current.  Tank centre tap 'vtk' fed from VDD through Rfd and AC-returned to the LNA VSS through Cct
(ideal elements in this screen); attenuator dump branch to vtk instead of VDD.  Schematic, ff 32C 3.35V, lowest-loss deg spiral.
usage: e3.py rfd_ohm cct_pF [dumpvdd]"""
import sys, re; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
rfd, cct = float(sys.argv[1]), float(sys.argv[2]); dumpvdd = len(sys.argv) > 3
def patch(t, variant='nom'):
    if not dumpvdd:
        t, n = re.subn(r'^(XMN\d+) VDD (cgd\d) ', r'\1 vtk \2 ', t, flags=re.M); assert n > 10, n
    i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
    nm = LS.NAMES[variant]
    return (t[:e] + f'Xlnaind_p vtk tank_p VSS {nm}\nXlnaind_n vtk tank_n VSS {nm}\nRfd VDD vtk {rfd}\nCct vtk VSS {cct}p\n' + t[e:] + '\n' + LS.subckt(variant))
tag = f'e3_r{rfd:g}_c{cct:g}' + ('_dv' if dumpvdd else '')
W = variant(tag, patch=patch, ind='none')
for st in (dict(), dict(att=63)):
    for kw in (dict(), dict(lsup=0.25e-9), dict(lsup=2e-9), dict(cdec=100e-12), dict(cdec=500e-12), dict(cdec=100e-12, lsup=2e-9), dict(cdec=300e-12, rdec=2.)):
        r = LM.stability(W, 'selftest', FF, deg='lowr', **st, **kw); print(tag, st, kw, fmt(r), flush=True)
