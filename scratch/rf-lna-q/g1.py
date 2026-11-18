"""G1: R+C extracted LNA (Magic extresist on the GDS, analog image; recipe of analog/wired_tx/wtx_mux8_layout.extract_rc) against the
C-only netlist: tt pad impedance, gain, NF on the real channel, current, stability rows on the package model (site B)."""
import sys, re; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import lna_close as L
rc = (Q / 'rc' / 'pt_lna_flat.rc.spice').read_text().replace('pt_lna_flat', 'pt_lna')
ref = (flow.GENERATED / 'lna.ext.spice').read_text()
pr = lambda t: re.search(r'(?mi)^\.subckt\s+pt_lna\s+(.*(?:\n\+.*)*)', t).group(1).replace('\n+', ' ').split()
print('ports equal:', pr(rc) == pr(ref), len(pr(rc)), len(pr(ref)), [a for a in pr(rc) if a not in pr(ref)][:6])
nr = sum(1 for l in rc.splitlines() if l.startswith('R')); print('resistors', nr, 'devices X', sum(1 for l in rc.splitlines() if l.startswith('X')), 'ref X', sum(1 for l in ref.splitlines() if l.startswith('X')))
(Q / 'rc' / 'lna_rc.spice').write_text(rc)
for name, base, like_rg in (('C-only + Rg 150 (extpr)', None, True), ('R+C, no added Rg', Q / 'rc' / 'lna_rc.spice', False), ('R+C + Rg 150', Q / 'rc' / 'lna_rc.spice', True)):
    if base is None:
        W = Q / 'w' / 'g1_ext'; v = 'extpr'
    else:
        if not like_rg: VIEW['extpr'] = (1e-3, 'nom', False, 0.)
        W = variant('g1_rc' + ('_rg' if like_rg else ''), base=base, like='extpr'); v = 'selftest'
        VIEW['extpr'] = (150., 'nom', False, 0.)
    u = tb.lna_ac(W, v, TT, f=2.44e9, ct=9); z = complex(u['zin_re_ohm'], u['zin_im_ohm']); m, _, _ = LM.channel_fit(z, d_mm=2.); m['ct'] = 9
    b = tb.lna_band(W, v, TT, m, ct=9); inb = [r for r in b['rows'] if 2.3999e9 <= r['f'] <= 2.48351e9]
    own = tb.lna_ac(W, v, TT, f=2.44e9, ct=9, match=tb.board_match(z, f=2.44e9), noiseless_load=True)
    print('%-26s idd %.2f mA Zpad %.1f%+.1fj S11 %.1f gain %.2f..%.2f NF %.2f..%.2f own %.2f (ideal-match gain %.2f)' % (name, u['idd_a'] * 1e3, z.real, z.imag, max(r['s11_db'] for r in b['rows']), min(r['gain_db'] for r in inb), max(r['gain_db'] for r in inb), min(r['nf_db'] for r in inb), max(r['nf_db'] for r in inb), own['nf_db'], own['gain_db']), flush=True)
    if base is not None and like_rg:
        for lob in (False, True):
            tb.set_lobias(lob); r = LM.stability(W, v, FF, deg='lowr', pkg='B_max', cdie=3e-9, rdie=0.03, rsw=0.2); tb.set_lobias(False)
            print('   stab B_max ff', 'lob' if lob else 'rx', fmt(r))
