"""E7: RF numbers of a schematic variant: Zin, ideal-lossless-match gain vs tank code, own NF (noiseless mixer model), current.
usage: e7.py tag [K=V mods] ; env VIEWS=extpr:tt,extpp:ss"""
import sys, os, json; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
tag = sys.argv[1]; mods = {k: eval(v) for k, v in (x.split('=', 1) for x in sys.argv[2:])}
C = {'tt': TT, 'ss': SS, 'ff': FF}
for vc in os.environ.get('VIEWS', 'extpr:tt,extpp:ss').split(','):
    v, c = vc.split(':'); c = C[c]
    W = variant(f'e7_{tag}_{v}', mods=mods, like=v)
    u = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=7); mi = tb.board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']), f=2.44e9)
    gs = [(ct, tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi)['gain_db']) for ct in (0, 3, 6, 9, 12, 15)]
    ct = max(gs, key=lambda x: x[1])[0]
    n = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi, noiseless_load=True)
    print(tag, v, c, 'Zin %.1f%+.1fj idd %.2f mA | gain vs ct %s | best ct %d NF_own %.2f dB' % (u['zin_re_ohm'], u['zin_im_ohm'], u['idd_a'] * 1e3, ' '.join('%d:%.2f' % g for g in gs), ct, n['nf_db']), flush=True)
