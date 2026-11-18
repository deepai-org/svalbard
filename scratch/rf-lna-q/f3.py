"""F3: no degeneration spirals + gate resistor value (bench substitution on the extracted netlist).  usage: f3.py rgw"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
rgw = sys.argv[1]
o = tb.with_pad_rf_pair
def w(text, block='lna'):
    t = o(text, block)
    if block == 'lna' and rgw != '82':
        assert t.count('r_width=82u r_length=1u') == 2; t = t.replace('r_width=82u r_length=1u', f'r_width={rgw}u r_length=1u')
    return t
tb.with_pad_rf_pair = w
tb.SRC_BOND = 'Rdsp srcp_b scm_b 0.02\nRdsn srcn_b scm_b 0.02\n'
W = Q / 'w' / f'f3_{rgw}'
for v, c, ct in (('extpr', TT, 6), ('extpr', ('ff', 22, 3.35), 12), ('extpr', SS, 6), ('extlo', ('ff', 22, 3.35), 6), ('extpp', SS, 12)):
    u = tb.lna_ac(W, v, c, f=2.44e9, ct=ct); z = complex(u['zin_re_ohm'], u['zin_im_ohm']); m, _, _ = LM.channel_fit(z, d_mm=2.); m['ct'] = ct
    b = tb.lna_band(W, v, c, m, ct=ct); inb = [r for r in b['rows'] if 2.3999e9 <= r['f'] <= 2.48351e9]
    print('rgw', rgw, v, c[0], 'Zpad %.1f%+.1fj S11 %.1f gain %.2f..%.2f NF %.2f..%.2f' % (z.real, z.imag, max(r['s11_db'] for r in b['rows']), min(r['gain_db'] for r in inb), max(r['gain_db'] for r in inb), min(r['nf_db'] for r in inb), max(r['nf_db'] for r in inb)), flush=True)
r = LM.stability(W, 'extpr', FF, deg='lowr', pkg='B_nom', cdie=3e-9, rdie=0.03, rsw=0.2); print('rgw', rgw, fmt(r))
