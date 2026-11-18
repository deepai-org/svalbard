"""F1 (round 2, item 1): which node carries the 47-66 MHz supply anti-resonance into the common mode?  Schematic, ff, lumped lossless
supply 3 nF / 0.03 ohm / 0.2 ohm switch / 2 nH per rail (the worst declared row: -9.8 ohm extracted).  usage: f1.py case [lob]"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
case = sys.argv[1]; lob = len(sys.argv) > 2
def add(lines):
    def p(t):
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i); return t[:e] + lines + '\n' + t[e:]
    return p
P = {'base': None, 'vcas': add('Cq1 vcas VSS 1u'), 'vg': add('Cq2 vg VSS 1u'), 'tailbias': add('Cq3 vtg VSS 1u\nCq4 vtc VSS 1u'),
     'pb': add('Cq5 pb VDD 1u'), 'cct': add('Cq6 vtk VSS 2n'), 'allbias': add('Cq1 vcas VSS 1u\nCq2 vg VSS 1u\nCq3 vtg VSS 1u\nCq4 vtc VSS 1u\nCq5 pb VDD 1u'),
     'vgr': add('Cq7 vgr VSS 1u')}
W = variant('f1_' + case, patch=P[case])
tb.set_lobias(lob)
for kw in (dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=2e-9, f1=5e6, f2=1e9, ppd=400), dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=1e-9)):
    r = LM.stability(W, 'selftest', FF, deg='lowr', **kw)
    print(case, 'lob' if lob else 'rx', 'LF' if 'f1' in kw else 'HF', 'Re_cm %.2f @ %.4g MHz | Re_diff %.2f' % (r['min_re_zcm_real_mixer_ohm'], r['f_min_re_zcm_hz'] / 1e6, r['min_re_zin_real_mixer_ohm']), flush=True)
    if 'f1' not in kw:
        import numpy as np
        f = sorted(W.glob('stab_selftest_*_cm0_zr.txt'), key=lambda p: p.stat().st_mtime)[-1]; d = np.array(S.read_table(f)); F = d[:, 0] / 1e9
        print('   cm curve', ' '.join('%g:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (0.5, 1, 1.5, 2, 2.4, 2.6, 3, 4, 5, 6, 8)))
