#!/usr/bin/env python3
"""Loop-inductance matrix of the west bond wires over the board ground (image method), for the LNA ground / RF input plan.
Geometry: ../bond/bond-audit.json model C (pad centre -> finger centre, die frame, mm); wire = two straight segments
pad (z 0) -> apex (h above the die face at fraction f of the plan span) -> finger (z = -H), 20.3 um diameter (0.8 mil).
Return = perfect ground plane at z = -H - zp (image wires with opposite current). L[i][j] = M(i,j) - M(i,image j).
  python3 bondl.py selftest      known answers + negative control
  python3 bondl.py               writes bondl.json and prints the tables"""
import json, math, sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
D = 0.0203; A = D / 2
def seg_pts(p, q, n):
    p, q = np.array(p, float), np.array(q, float); t = (np.arange(n) + .5) / n
    return p + np.outer(t, q - p), (q - p) / n
def M_num(s1, s2, n=400):
    """Neumann mutual (nH, mm) between two straight filaments, midpoint rule; r floored at the GMD of the wire."""
    x1, d1 = seg_pts(*s1, n); x2, d2 = seg_pts(*s2, n)
    r = np.sqrt(((x1[:, None, :] - x2[None, :, :]) ** 2).sum(-1) + A ** 2)   # high-frequency: current on the surface (skin depth 1.7 um at 2.4 GHz), no internal inductance
    return 0.1 * float(d1 @ d2) * float((1 / r).sum())
def L_seg(l): return 0.2 * l * (math.log(2 * l / A) - 1.0)           # partial self inductance, straight round wire, high-frequency limit (Rosa: -0.75 at DC), nH, mm
def wire_segs(src, dst, h, f, H):
    ax = [src[0] + f * (dst[0] - src[0]), src[1] + f * (dst[1] - src[1]), h]
    return [((src[0], src[1], 0.), tuple(ax)), (tuple(ax), (dst[0], dst[1], -H))]
def image(segs, zpl): return [((a[0], a[1], 2 * zpl - a[2]), (b[0], b[1], 2 * zpl - b[2])) for a, b in segs]
def partial(wi, wj, same):
    tot = 0.
    for a, sa in enumerate(wi):
        for b, sb in enumerate(wj):
            if same and a == b: tot += L_seg(math.dist(*sa))
            else: tot += M_num(sa, sb)
    return tot
def matrix(wires, zpl, sign=-1.):
    n = len(wires); L = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            v = partial(wires[i], wires[j], i == j)
            if zpl is not None: v += sign * partial(wires[i], image(wires[j], zpl), False)
            L[i, j] = L[j, i] = v
    return L
if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
    ok = True
    # 1. straight 20 mm wire 0.4 mm over a plane: 0.2 l ln(4h/d) (long-wire limit; end effect < 3 %)
    w = [[((0, 0, .4), (10, 0, .4)), ((10, 0, .4), (20, 0, .4))]]
    got = matrix(w, 0.)[0, 0]; ref = 0.2 * 20 * math.log(4 * .4 / D); print('wire over plane', round(got, 3), 'ref', round(ref, 3)); ok &= abs(got / ref - 1) < .03
    # 2. two parallel 2 mm filaments 0.211 mm apart, free space: Grover M = 0.2 l (ln(l/d + sqrt(1+l2/d2)) - sqrt(1+d2/l2) + d/l)
    l, d = 2., .211; ref = 0.2 * l * (math.log(l / d + math.sqrt(1 + l * l / d / d)) - math.sqrt(1 + d * d / l / l) + d / l)
    got = M_num(((0, 0, 0), (2, 0, 0)), ((0, d, 0), (2, d, 0))); print('parallel M', round(got, 4), 'ref', round(ref, 4)); ok &= abs(got / ref - 1) < .01
    # 3. self of a 2.6 mm straight wire split in two segments = Rosa of the whole
    got = matrix([[((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2.6, 0, 0))]], None)[0, 0]; ref = L_seg(2.6); print('split self', round(got, 4), 'ref', round(ref, 4)); ok &= abs(got / ref - 1) < .02
    # negative control: image with the wrong sign must NOT reproduce case 1
    bad = matrix(w, 0., sign=+1.)[0, 0]; print('negative control (image sign +):', round(bad, 3), 'must differ from', round(0.2 * 20 * math.log(4 * .4 / D), 3)); ok &= abs(bad / (0.2 * 20 * math.log(4 * .4 / D)) - 1) > .5
    print('SELFTEST', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
W0 = {w['bond']: w for w in json.load(open(HERE + '/../bond/bond-audit.json'))['models']['C']['wires']}
NAME = {63: 'GND63', 64: 'PWR_AUX_1', 65: 'BB_Q_N', 66: 'BB_Q_P', 67: 'BB_I_N', 68: 'BB_I_P', 69: 'RF_RX_N', 70: 'RF_RX_P', 71: 'GND71', 72: 'VDD_CORE_1', 73: 'GND73', 74: 'VDD_IO_3'}
B = sorted(NAME)
# loop / plane cases. H = die + attach. Plane: 'paddle' = F.Cu paddle level under the die (z = -H; only valid if board ground copper is under the wire: run-2 board),
# 'in1' = In1 plane 0.196 mm + 0.0175 below the finger surface (run-1 board, pour excluded inside the finger ring), 'none' = partial inductance (upper bound)
CASES = {'min': dict(h=.10, f=.25, H=.275, zpl=-.275), 'nom': dict(h=.15, f=.25, H=.285, zpl=-.285 - .2135), 'max': dict(h=.30, f=.35, H=.300, zpl=None)}
if __name__ != "__main__": pass
else:
    out = dict(bonds=B, names=[NAME[b] for b in B], cases={})
    for c, p in CASES.items():
        wires = [wire_segs(W0[b]['src'], W0[b]['dst'], p['h'], p['f'], p['H']) for b in B]
        L = matrix(wires, p['zpl']); k = L / np.sqrt(np.outer(np.diag(L), np.diag(L)))
        out['cases'][c] = dict(params=p, L_nH=L.round(4).tolist(), k=k.round(4).tolist())
        ix = {b: i for i, b in enumerate(B)}
        def par(group):          # all wires of the group driven in parallel (same voltage), others open
            idx = [ix[b] for b in group]; Y = np.linalg.inv(L[np.ix_(idx, idx)]); return 1 / Y.sum()
        def loop(sig, ret):      # signal wires in parallel carrying +I, return wires in parallel carrying -I, shared end nodes (both ends common)
            idx = [ix[b] for b in sig + ret]; Ls = L[np.ix_(idx, idx)]; n = len(idx); ns = len(sig)
            # unknown currents i, voltages: v_s on the signal group, v_r on the return group; sum i_s = 1, sum i_r = -1; L = v_s - v_r
            Am = np.zeros((n + 2, n + 2)); Am[:n, :n] = Ls; Am[:ns, n] = -1; Am[ns:n, n + 1] = -1; Am[n, :ns] = 1; Am[n + 1, ns:n] = 1
            x = np.linalg.solve(Am, np.r_[np.zeros(n), 1, -1]); return x[n] - x[n + 1]
        P, N = ix[70], ix[69]
        r = dict(
            self_RXP=L[P, P], self_RXN=L[N, N], M_PN=L[P, N], k_PN=k[P, N],
            Ldiff_per_leg=(L[P, P] + L[N, N]) / 2 - L[P, N], Lcm_pair=(L[P, P] + L[N, N] + 2 * L[P, N]) / 4,
            gnd71=L[ix[71], ix[71]], gnd71_73=par([71, 73]), gnd71_73_63=par([63, 71, 73]), gnd_plus_vdd_71_72_73_74=par([71, 72, 73, 74]),
            M_P_71=L[P, ix[71]], M_N_71=L[N, ix[71]], M_P_68=L[P, ix[68]], M_N_68=L[N, ix[68]], M_P_72=L[P, ix[72]], M_N_72=L[N, ix[72]], M_P_73=L[P, ix[73]], M_N_73=L[N, ix[73]],
            cm_loop_pair_vs_71=loop([70, 69], [71]), cm_loop_pair_vs_71_73=loop([70, 69], [71, 73]), cm_loop_pair_vs_71_72_73_74=loop([70, 69], [71, 72, 73, 74]),
            se_loop_P_vs_71=loop([70], [71]), se_loop_N_vs_71=loop([69], [71]), se_loop_P_vs_71_73=loop([70], [71, 73]), se_loop_N_vs_71_73=loop([69], [71, 73]))
        out['cases'][c]['derived_nH'] = {a: round(float(v), 4) for a, v in r.items()}
    json.dump(out, open(HERE + '/bondl.json', 'w'), indent=1)
    for c in CASES:
        print('==', c, CASES[c]); d = out['cases'][c]
        print('      ' + ' '.join(f'{b:6d}' for b in B))
        for b, row in zip(B, d['L_nH']): print(f'{b:5d} ' + ' '.join(f'{v:6.3f}' for v in row), NAME[b])
        for a, v in d['derived_nH'].items(): print(f'   {a:32s} {v:7.3f}')
