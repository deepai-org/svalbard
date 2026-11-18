"""Lever table: geometry-only dry runs of le.generate (Magic stubbed), new hop plan.  usage: python3 levers.py"""
import dry, wl, ser8d_macro as D, serq8_macro as Q
le = dry.le
H = {k: [f'H{k}_{i}' for i in range(len(s))] for k, s in D.HOPS.items()}
Hs = lambda *ks: [h for k in ks for h in H[k]]
P = [f'P{k}' for k in range(8)]
old = [['L0'] + H[0] + ['L1'] + H[1] + ['L2'] + H[2] + ['CK', 'CTL'], P, ['L3'] + H[3] + ['L4'] + H[4] + ['L5'] + H[5], ['L6'] + H[6] + ['L7'] + H[7] + ['DV']]
LA, LB = ['L0', 'L1', 'L2', 'L3'], ['L4', 'L5', 'L6', 'L7']
tf = dict(track_first=list(Q.PH))
quiet = {n: 0.02 for n in list(Q.PH) + [f'F{k}' for k in range(8)] + [f'Q{k}' for k in range(8)] + [c[1] for i, _, c in D.top_instances() if i[:2] == 'XH']}
V = [
 ('0 s12 row plan, channels above rows', old, {}),
 ('1 s12 row plan + over_cell', old, dict(over_cell=True)),
 ('2 regs 4+4, hops+DV+CK+CTL row, P row top', [LA, LB, ['CK', 'CTL', 'DV'] + Hs(0, 4, 1, 5, 2, 6, 3, 7), P], dict(over_cell=True)),
 ('3 = 2 with hop groups at BO columns (rows())', D.rows(), dict(over_cell=True)),
 ('4 = 3 + PH track_first', D.rows(), dict(over_cell=True, em=tf)),
 ('5 = 4 + quiet trunks (FINAL)', D.rows(), dict(over_cell=True, em=tf, net_space=quiet)),
 ('6 three rows (wider)', [LA + H[0] + H[1] + H[2] + H[3] + ['CK', 'CTL'], P + ['DV'], LB + H[4] + H[5] + H[6] + H[7]], dict(over_cell=True)),
 ('7 two P rows', [LA, LB, P[:4] + Hs(0, 1, 2, 3, 4), P[4:] + ['DV', 'CK', 'CTL'] + Hs(5, 6, 7)], dict(over_cell=True)),
 ('8 = 5 without D0..D39 trunks to the top edge', D.rows(), dict(over_cell=True, em=tf, net_space=quiet, _noD=True)),
]
for tag, rows, kw in V:
    wl.show(tag, rows, **kw)
le.TRACK_SPACE = 0.28
wl.show('9 = 5 with track space 0.28 (engine constant, NOT built)', D.rows(), over_cell=True, em=tf, net_space=quiet)
