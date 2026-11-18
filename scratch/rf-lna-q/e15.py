"""E15: extracted LNA on the REAL channel (ngspice, lossy ladder): numpy fit vs ngspice S11/gain/NF; negative control; timing of
one chain_det point.  usage: e15.py view corner d_mm [chain lo]"""
import sys, time, json; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
C = {'tt': TT, 'ss': SS, 'ff': FF}
v, c, d = sys.argv[1], C[sys.argv[2]], float(sys.argv[3]); W = Q / 'w' / f'e15_{v}_{sys.argv[2]}_{d:g}'
ct = {('extpr', 'typical'): 9, ('extpp', 'ss'): 12, ('extpr', 'ss'): 6}.get((v, c[0]), 9)
u = tb.lna_ac(W, v, c, f=2.44e9, ct=ct); z = complex(u['zin_re_ohm'], u['zin_im_ohm'])
m, s11, loss = LM.channel_fit(z, d_mm=d); m['ct'] = ct
print(v, c, 'Zpad %.1f%+.1fj fit %s S11 %.1f loss %.2f dB' % (z.real, z.imag, m['parts'], s11, loss), flush=True)
b = tb.lna_band(W, v, c, m, ct=ct); rows = [r for r in b['rows'] if 2.3999e9 <= r['f'] <= 2.48351e9]
g0 = tb.lna_ac(W, v, c, f=2.44e9, ct=ct, match=tb.board_match(z, f=2.44e9))
print('  ngspice: S11 worst %.1f dB | gain %.2f..%.2f dB (ideal lossless match %.2f -> loss %.2f dB) | NF incl. channel %.2f..%.2f dB' % (max(r['s11_db'] for r in b['rows']), min(r['gain_db'] for r in rows), max(r['gain_db'] for r in rows), g0['gain_db'], g0['gain_db'] - max(r['gain_db'] for r in rows), min(r['nf_db'] for r in rows), max(r['nf_db'] for r in rows)), flush=True)
if len(sys.argv) > 4:
    lo = None if sys.argv[5] == 'ideal' else tb.LO_REAL[sys.argv[5]]; t0 = time.time()
    r = tb.chain_det(W / f'ch_{sys.argv[5]}', v, c, ct=ct, match=m, lo=lo)
    r = {k: x for k, x in r.items() if k not in ('detail', 'tones')}; r['seconds'] = round(time.time() - t0)
    json.dump(r, open(Q / f'e15_{v}_{sys.argv[2]}_{d:g}_{sys.argv[5]}.json', 'w'), indent=1, default=str)
    print('  CHAIN', sys.argv[5], {k: r.get(k) for k in ('nf_dsb_db', 'nf_ssb_db', 'gain_sig_db', 'f_parts', 'seconds')}, flush=True)
