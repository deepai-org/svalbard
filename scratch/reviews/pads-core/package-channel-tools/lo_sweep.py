import json, math, cmath, sys
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/spec')
import placement as pl
g = pl.geo
def leg(p, place, f, C, db=0.0):
    M, _ = pl.chain_to(p, f, place, db)
    Zd = 1 / (1j * 2 * math.pi * f * C + 1 / 5e3)
    return 2 * pl.deliver(pl.rev(M), Zd)[1]
res = {}
for C in (0.7e-12, 1.0e-12, 1.5e-12, 2.0e-12):
    for place in ('conn+2mm', 'car30mm'):
        row = {}
        for f in (2.40e9, 2.45e9, 2.50e9):
            I = leg(g['REF_IN'], place, f, C) + leg(g['REF_IN_N'], place, f, C)
            Q = leg(g['AUX_CLK_P'], place, f, C) + leg(g['AUX_CLK_N'], place, f, C)
            row[f'{f/1e9:.2f}'] = dict(I_diff_gain=round(abs(I) / 2, 2), Q_diff_gain=round(abs(Q) / 2, 2),
                                       IQ_phase_deg=round(math.degrees(cmath.phase(Q / I)), 1),
                                       IQ_amp_dB=round(20 * math.log10(abs(Q) / abs(I)), 2))
        sp = [abs(leg(g['REF_IN'], place, 2.45e9, C, d) + leg(g['REF_IN_N'], place, 2.45e9, C, d)) / 2 for d in (-0.3, 0, 0.3)]
        row['bond_pm0p3_dB'] = round(20 * math.log10(max(sp) / min(sp)), 2)
        res[f'C{C*1e12:.1f}pF_{place}'] = row
json.dump(res, open('lo_sweep.json', 'w'), indent=1)
for k, v in res.items(): print(k, v)
