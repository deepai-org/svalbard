import json, math, cmath, sys
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/spec')
import placement as pl
g = pl.geo
def leg(p, f, C, R, db=0.0, place='car30mm'):
    M, _ = pl.chain_to(p, f, place, db)
    return 2 * pl.deliver(pl.rev(M), 1 / (1j * 2 * math.pi * f * C + 1 / R))[1]
out = {}
for R in (5e3, 200, 100, 50):
    gains = [abs(leg(g['REF_IN'], 2.45e9, C, R) + leg(g['REF_IN_N'], 2.45e9, C, R)) / 2 for C in (0.7e-12, 1.0e-12, 1.5e-12, 2.0e-12)]
    ph = [math.degrees(cmath.phase((leg(g['AUX_CLK_P'], 2.45e9, C, R) + leg(g['AUX_CLK_N'], 2.45e9, C, R)) /
                                   (leg(g['REF_IN'], 2.45e9, C, R) + leg(g['REF_IN_N'], 2.45e9, C, R)))) for C in (0.7e-12, 1.5e-12)]
    out[f'R{R:g}'] = dict(gain_C0p7_1_1p5_2pF=[round(x, 2) for x in gains], spread_dB=round(20 * math.log10(max(gains) / min(gains)), 1),
                          IQ_phase_deg=[round(x, 1) for x in ph])
print(json.dumps(out, indent=0))
sk = {}
v = 1e3 / 299.792 * math.sqrt(pl.cm.EEFF)  # ps/mm
for a, b in [('RF_RX_P', 'RF_RX_N'), ('RF_TX_P', 'RF_TX_N'), ('REF_IN', 'REF_IN_N'), ('AUX_CLK_P', 'AUX_CLK_N'),
             ('WIRE_RX_P', 'WIRE_RX_N'), ('WIRE_TX_P', 'WIRE_TX_N'), ('WTX_EXT_P', 'WTX_EXT_N'),
             ('BB_I_P', 'BB_I_N'), ('BB_Q_P', 'BB_Q_N')]:
    la = g[a]['f_mm'] + g[a]['b_mm']; lb = g[b]['f_mm'] + g[b]['b_mm']
    sk[f'{a[:-2] if a.endswith("_P") else a}'] = dict(P_mm=round(la, 2), N_mm=round(lb, 2), skew_ps=round((la - lb) * v, 1),
                                                      bond_P=g[a]['bond_mm'], bond_N=g[b]['bond_mm'])
for k in ('D2H', 'H2D'):
    ls = {s: g[s]['f_mm'] + g[s]['b_mm'] for s in g if s.startswith(k)}
    sk[k + '_group'] = dict(min_mm=round(min(ls.values()), 2), max_mm=round(max(ls.values()), 2),
                            clk_mm=round(ls[k + '_CLK'], 2), spread_ps=round((max(ls.values()) - min(ls.values())) * v, 1))
print(json.dumps(sk, indent=0)); json.dump(dict(lo_term=out, skew=sk, ps_per_mm=round(v, 2)), open('lo_term_skew.json', 'w'), indent=1)
