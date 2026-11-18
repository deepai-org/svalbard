#!/usr/bin/env python3
"""RF_RX site options on the west edge: differential pickup from ground / supply bond currents and from the external-LO pairs.
Uses bondl.py (same wire model, loop cases min / nom / max). Metric per aggressor bond k and RX pair (p, n): dM = M(p,k) - M(n,k) [nH];
bounce conversion = dM / L_kk (the differential EMF in the RX bond loop per volt of bounce across bond k, both due to the same current)."""
import json, math, sys, os
import numpy as np
import bondl as b
W0 = b.W0
west = list(range(55, 75)); south = list(range(1, 10)); B = west + south; ix = {k: i for i, k in enumerate(B)}
GND = [57, 63, 71, 73, 9]; SUP = [58, 64, 72, 74]     # bond 9 = south dvss_pads[0]; 58 VDD_IO_2, 64 PWR_AUX_1, 72 VDD_CORE_1, 74 VDD_IO_3
SOUTH_SIG = [1, 2, 3, 4, 5, 6, 7, 8]                 # D2H_D[0], RESET_N, D2H_D[1..5], D2H_CLK (host-link outputs next to the SW corner)
OPTS = {'A today: RX 69/70': dict(rx=(70, 69)), 'B: RX 67/68 (swap with BB_I)': dict(rx=(68, 67)), 'C: RX 65/66 (swap with BB_Q)': dict(rx=(66, 65))}
LO = {'AUX_CLK 62/61': (62, 61), 'REF_IN 60/59': (60, 59)}
res = {}
for c, p in b.CASES.items():
    wires = [b.wire_segs(W0[k]['src'], W0[k]['dst'], p['h'], p['f'], p['H']) for k in B]
    L = b.matrix(wires, p['zpl']); res[c] = {}
    for name, o in OPTS.items():
        P, N = ix[o['rx'][0]], ix[o['rx'][1]]
        dm = lambda k: L[P, ix[k]] - L[N, ix[k]]
        r = dict(dM_gnd={k: round(dm(k), 4) for k in GND}, dM_sup={k: round(dm(k), 4) for k in SUP}, dM_south={k: round(dm(k), 4) for k in SOUTH_SIG},
                 conv_gnd={k: round(dm(k) / L[ix[k], ix[k]], 4) for k in GND}, conv_sup={k: round(dm(k) / L[ix[k], ix[k]], 4) for k in SUP})
        r['conv_gnd_sum_signed'] = round(sum(r['conv_gnd'].values()), 4); r['conv_gnd_sum_abs'] = round(sum(abs(v) for v in r['conv_gnd'].values()), 4)
        r['conv_all_sum_abs'] = round(r['conv_gnd_sum_abs'] + sum(abs(v) for v in r['conv_sup'].values()), 4)
        r['dM_south_sum_abs'] = round(sum(abs(v) for v in r['dM_south'].values()), 4)
        r['lo_Mdd_nH'] = {n: round(L[P, ix[a]] - L[P, ix[bb]] - L[N, ix[a]] + L[N, ix[bb]], 4) for n, (a, bb) in LO.items()}
        r['Ldiff_leg'] = round((L[P, P] + L[N, N]) / 2 - L[P, N], 3); r['k_PN'] = round(L[P, N] / math.sqrt(L[P, P] * L[N, N]), 3)
        res[c][name] = r
json.dump(res, open(os.path.dirname(os.path.abspath(__file__)) + '/mapopt.json', 'w'), indent=1)
db = lambda x: 20 * math.log10(abs(x)) if x else -999
for name in OPTS:
    print('==', name)
    for c in b.CASES:
        r = res[c][name]
        print(f'  {c}: conv gnd per bond {r["conv_gnd"]}  sum signed {db(r["conv_gnd_sum_signed"]):.1f} dB, sum abs {db(r["conv_gnd_sum_abs"]):.1f} dB; with supplies abs {db(r["conv_all_sum_abs"]):.1f} dB')
        print(f'      conv sup {r["conv_sup"]}; south dM (nH) {r["dM_south"]} sum abs {r["dM_south_sum_abs"]}; LO Mdd (nH) {r["lo_Mdd_nH"]}; Ldiff/leg {r["Ldiff_leg"]} k {r["k_PN"]}')
