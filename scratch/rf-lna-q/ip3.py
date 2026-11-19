"""IIP3 over corners (round 3): metal-aware LNA (RFRX_LNA_SRC=rext), view extpr, real channel with the per-chip carrier fit, x2 TIA
with hib = 1, ideal square LO (the linearity bench has no delivered-LO option), max gain. Two tone powers per corner (-40 / -34 dBm)
to check the 3:1 slope; IIP3 from the lower power. Limit (declared): >= -10 dBm. usage: RFRX_LNA_SRC=rext python3 ip3.py <corner>"""
import sys, os, json, math
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
from pathlib import Path
import tb, lna_match as LM, linearity as LIN
C = {'tt': ('typical', 27, 3.3), 'ss': ('ss', 32, 3.15), 'ff': ('ff', 32, 3.35)}[sys.argv[1]]
W = Path('/home/ubuntu/svalbard/scratch/rf_rx/ip3') / sys.argv[1]; W.mkdir(parents=True, exist_ok=True); os.chdir(W)
ct = {'typical': 9, 'ss': 6, 'ff': 9}[C[0]]
u = tb.lna_ac(W, 'extpr', C, f=2.44e9, ct=ct); m, _, _ = LM.channel_fit(complex(u['zin_re_ohm'], u['zin_im_ohm']), d_mm=2.); m['ct'] = ct
LIN.deck.__defaults__ = (C, 'extpr')
LO = 2.4e9; out = []
g = LIN.run(f'{sys.argv[1]}_ref', [(LO + 3e6, -60.)], [3e6], m, corner=C)[3e6] / LIN.emf(-60.)
for p in (-40., -34.):
    r = LIN.run(f'{sys.argv[1]}_{int(-p)}', [(LO + 20e6, p), (LO + 37e6, p), (LO + 3e6, -200)], [20e6, 37e6, 3e6], m, corner=C)
    pin_im3 = 20 * math.log10(r[3e6] / g / LIN.emf(p)) + p
    out.append(dict(p_dbm=p, im3_out_v=r[3e6], gain_3mhz_db=20 * math.log10(g), im3_in_dbm=pin_im3, iip3_dbm=p + (p - pin_im3) / 2))
json.dump(dict(corner=C, rows=out, slope_db_per_db=(20 * math.log10(out[1]['im3_out_v'] / out[0]['im3_out_v'])) / 6.), open('ip3.json', 'w'), indent=1)
print(sys.argv[1], out)
