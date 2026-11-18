"""E12: damping resistor Rp in parallel with each degeneration spiral (bench-level screen).  usage: e12.py rp [mods]"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import numpy as np
rp = float(sys.argv[1]); mods = {k: eval(v) for k, v in (x.split('=', 1) for x in sys.argv[2:])}
tag = f'e12_rp{rp:g}' + ''.join(f'_{k[4:]}{v}' for k, v in mods.items())
def src(variant):
    n = LS.DEG_NAMES[variant]
    return f'Xdegp srcp_b scm_b {{gnd}} {n}\nXdegn srcn_b scm_b {{gnd}} {n}\n' + (f'Rdp srcp_b scm_b {rp}\nRdn srcn_b scm_b {rp}\n' if rp else '') + LS.subckt_deg(variant)
W = variant(tag, mods=mods)
tb.SRC_BOND = src('lowr')
r = LM.stability(W, 'selftest', FF, deg='lowr'); print(tag, fmt(r).replace('mu 1.0000 ', ''), flush=True)
f = sorted(W.glob('stab_selftest_*_mx0_zr.txt'))[-1]; d = np.array(S.read_table(f)); F = d[:, 0] / 1e9
print(tag, 'dm', ' '.join('%g:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (2.4, 4, 6, 8, 10, 11, 12, 13, 14, 16, 20, 25, 30)))
for v, c in (('extpr', TT), ('extpp', SS)):
    W = variant(tag + '_' + v, mods=mods, like=v); tb.SRC_BOND = src(tb.LNA_DEG_VIEW.get(v, 'nom'))
    u = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=7); mi = tb.board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']), f=2.44e9)
    ct = 6 if v == 'extpr' else 9
    g = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi); n = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi, noiseless_load=True)
    print(tag, v, 'Zin %.1f%+.1fj gain %.2f NF_own %.2f' % (u['zin_re_ohm'], u['zin_im_ohm'], g['gain_db'], n['nf_db']), flush=True)
