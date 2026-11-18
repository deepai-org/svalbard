"""E4: tail (true differential pair) + CM-only loss network + optional local load return.  Ideal-element screen, schematic LNA.
usage: e4.py ct_pF rt_ohm ccm_pF rcm_ohm [rfd cct_pF] ; ccm=0 -> no CM network ; rfd=0 -> tank on VDD
env CASES=quick|full  NODE=pad|gate"""
import sys, re, os; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
a = [float(x) for x in sys.argv[1:]] + [0, 0]
ct, rt, ccm, rcm, rfd, cct = a[:6]
node = os.environ.get('NODE', 'pad'); corner = {'ff': FF, 'tt': TT, 'ss': SS}[os.environ.get('CORNER', 'ff')]
def patch(t, variant='nom'):
    i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
    nm = LS.NAMES[variant]; add = ''
    if rfd:
        t, n = re.subn(r'^(XMN\d+) VDD (cgd\d) ', r'\1 vtk \2 ', t, flags=re.M); assert n > 10, n
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
        add += f'Xlnaind_p vtk tank_p VSS {nm}\nXlnaind_n vtk tank_n VSS {nm}\nRfd VDD vtk {rfd}\nCct vtk VSS {cct}p\n'
    else:
        add += f'Xlnaind_p VDD tank_p VSS {nm}\nXlnaind_n VDD tank_n VSS {nm}\n'
    if ccm:
        n1, n2 = ('rf_in_p', 'rf_in_n') if node == 'pad' else ('g_p', 'g_n')
        add += f'Ccmp {n1} ncm {ccm}p\nCcmn {n2} ncm {ccm}p\nRcm ncm VSS {rcm}\n'
    return t[:e] + add + t[e:] + '\n' + LS.subckt(variant)
tag = f'e4_{node}_ct{ct:g}_rt{rt:g}_c{ccm:g}_r{rcm:g}_f{rfd:g}_{cct:g}'
W = variant(tag, patch=patch, ind='none')
n = LS.DEG_NAMES['lowr']
tb.SRC_BOND = (f'Xdegp srcp_b scm {{gnd}} {n}\nXdegn srcn_b scm {{gnd}} {n}\nItail scm {{gnd}} DC 18m\nRtail scm {{gnd}} {rt}\nCtail scm {{gnd}} {ct}p\n' + LS.subckt_deg('lowr'))
full = os.environ.get('CASES', 'quick') == 'full'
sup = [dict(), dict(lsup=0.25e-9), dict(lsup=2e-9), dict(cdec=100e-12), dict(cdec=500e-12), dict(cdec=100e-12, lsup=2e-9), dict(cdec=500e-12, lsup=0.25e-9)] if full else [dict(), dict(cdec=500e-12), dict(lsup=2e-9)]
for st in ((dict(), dict(att=63), dict(mode='bypass')) if full else (dict(),)):
    for kw in sup:
        r = LM.stability(W, 'selftest', corner, deg='lowr', **st, **kw); print(tag, st, kw, fmt(r), flush=True)
