#!/usr/bin/env python3
"""Supply current / IR / EM check on the exported routed geometry.

usage: supply_ir.py <workdir> [<VDD_mA override>]

Resistor network per supply net: one node per routed rectangle, edges between
overlapping same-layer rectangles (centre-to-centre sheet resistance) and
through via cuts. Resistances use the gf180mcu_fd_sc_mcu7t5v0__max.tlef
corner (Metal1-4 0.104, Metal5 0.070 ohm/sq, 15 ohm per Via cut), not nominal.
The boundary pin is the source. Equal current share is drawn at every terminal;
the node-voltage solve gives the IR drop (<= 10 mV) and every branch current.

EM limits are the GF180MCU design manual (DRM section 14.2) unidirectional
values. Gate: 85 C column (the stress-safe envelope of tapeout-plan.md is
0-85 C, operating 22-32 C): Via1-4 0.58 mA/cut (Table 14.4), Metal1-4
2.09 mA/um, Metal5 (11 kA top metal) 4.5 mA/um (Table 14.3). Reported, not
gated: utilisation against the 125 C column, which is what the PDK tech LEF
DCCURRENTDENSITY encodes (0.18 mA/cut, 0.67 / 1.5 mA/um).

Currents (not assumed margins):
  VDD     1.0 mA  = blocks.bias.resource_allocation.current_budget_ma (analog-architecture.json),
                    the same in every mode
  RAIL_x  (active outputs + 1 TRK diode branch) x 12.14 uA x 2; each pt_bias_bankN
          leg is the same 2 x 5/4 um PMOS as the TRK diode (pt_core_bias.spice),
          12.14 uA = maximum pre-trim output (tapeout-readiness core bias entry);
          bank_pll has its 4th (lc_vco_reserved) enable tied off, counted anyway
  VSS     VDD + sum of rail currents (every rail returns through VSS)
Reported (not gated): the bound with the whole net current at the single
worst terminal, I_total * R_eff(pin, terminal). Masters' internal resistance
is excluded.
"""
import json, sys
from pathlib import Path
import numpy as np

work = Path(sys.argv[1]); i_vdd = float(sys.argv[2])*1e-3 if len(sys.argv) > 2 else 1.0e-3
RS = {'Metal1': .104, 'Metal2': .104, 'Metal3': .104, 'Metal4': .104, 'Metal5': .070}; RVIA = 15.0  # max-corner tech LEF
J_LIMIT = {'Metal1': 2.09e-3, 'Metal2': 2.09e-3, 'Metal3': 2.09e-3, 'Metal4': 2.09e-3, 'Metal5': 4.5e-3}  # A/um, DRM T14.3 85 C
J_125 = {'Metal1': .67e-3, 'Metal2': .67e-3, 'Metal3': .67e-3, 'Metal4': .67e-3, 'Metal5': 1.5e-3}  # A/um, DRM 125 C / tech LEF
CUT_LIMIT = 0.58e-3  # A per 0.26 um Via1-4 cut, DRM T14.4 unidirectional 85 C
CUT_125 = 0.18e-3  # A per cut, DRM 125 C / tech LEF DCCURRENTDENSITY
IR_LIMIT = .010  # V, 0.3 % of 3.3 V
w = json.loads((work/'routed.json').read_text()); u = w['dbu_per_um']
import os
inp = Path(os.environ.get('CORE_BIAS_INPUT', str(work.parents[0]/'core-bias-physical-terminals-current')))
terms = json.loads((inp/'physical-terminals.json').read_text())


def overlap(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def half_r(box, layer, toward):
    # resistance from rectangle centre to point `toward` along its long axis
    wx, wy = (box[2]-box[0])/u, (box[3]-box[1])/u; cx, cy = (box[0]+box[2])/2/u, (box[1]+box[3])/2/u
    if wx >= wy:
        return RS[layer]*abs(toward[0]-cx)/wy
    return RS[layer]*abs(toward[1]-cy)/wx


# Rails feed one pt_bias_bankN each: N output legs + the TRK diode leg.
RAIL_A = {r: (n+1)*12.14e-6*2 for r, n in dict(RAIL_rf=8, RAIL_conv=5, RAIL_pll=4, RAIL_wired=3, RAIL_debug=3).items()}
NET_A = dict(VDD=i_vdd, VSS=i_vdd+sum(RAIL_A.values()), **RAIL_A)
out = {}; ok = True
for name in ['VDD', 'VSS', 'RAIL_rf', 'RAIL_conv', 'RAIL_pll', 'RAIL_wired', 'RAIL_debug']:
    net = w['nets'][name]; I = NET_A[name]
    metal = [(s['layer'], s['box_dbu']) for s in net['shapes'] if s['layer'].startswith('Metal')]
    metal += [(p['layer'], p['box_dbu']) for p in net['pins']]
    pin_nodes = list(range(len(metal)-len(net['pins']), len(metal)))
    cuts = [(int(s['layer'][-1]), s['box_dbu']) for s in net['shapes'] if s['layer'].startswith('Via')]
    n = len(metal); G = np.zeros((n, n))
    # A rectangle lying entirely inside a larger same-layer rectangle (via
    # landing pads inside a 2 um trunk) is the same merged metal: collapse it
    # into its container so it is neither a resistor nor a narrow EM branch.
    inside = lambda a, b: b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]
    area = lambda b: (b[2]-b[0])*(b[3]-b[1])
    rep = list(range(n))
    for i in range(n):
        cont = [j for j in range(n) if j != i and metal[j][0] == metal[i][0] and inside(metal[i][1], metal[j][1])
                and (area(metal[j][1]) > area(metal[i][1]) or j < i)]
        if cont:
            rep[i] = max(cont, key=lambda j: area(metal[j][1]))
    for _ in range(n):
        nxt = [rep[rep[i]] for i in range(n)]
        if nxt == rep:
            break
        rep = nxt
    collapsed = sum(1 for i in range(n) if rep[i] != i)

    def add(i, j, r):
        g = 1/max(r, 1e-3); G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
    for i in range(n):
        for j in range(i+1, n):
            if rep[i] == i and rep[j] == j and metal[i][0] == metal[j][0] and overlap(metal[i][1], metal[j][1]):
                a, b = metal[i][1], metal[j][1]
                pt = ((max(a[0], b[0])+min(a[2], b[2]))/2/u, (max(a[1], b[1])+min(a[3], b[3]))/2/u)
                add(i, j, half_r(a, metal[i][0], pt)+half_r(b, metal[j][0], pt))
    vcount = {}
    for level, c in cuts:
        lo = [rep[i] for i, (l, b) in enumerate(metal) if l == f'Metal{level}' and overlap(b, c)]
        hi = [rep[i] for i, (l, b) in enumerate(metal) if l == f'Metal{level+1}' and overlap(b, c)]
        if lo and hi:
            # widest landing rectangle on each side carries the cut
            a = max(lo, key=lambda k: min(metal[k][1][2]-metal[k][1][0], metal[k][1][3]-metal[k][1][1]))
            b = max(hi, key=lambda k: min(metal[k][1][2]-metal[k][1][0], metal[k][1][3]-metal[k][1][1]))
            add(a, b, RVIA); vcount[(min(a, b), max(a, b))] = vcount.get((min(a, b), max(a, b)), 0)+1
    # terminal nodes: route rectangles touching each audited terminal shape
    tnodes = []
    for t in terms['nets'][name]:
        # Supply pins own the master metal touching the audited rectangle
        # (precise_lefs.py, clipped to a 3 um halo), so a route landing on
        # that rail within 3 um counts; master rail resistance is ignored.
        hit = [rep[i] for i, (l, b) in enumerate(metal) for s in t['shapes']
               if l == s['layer'] and overlap(b, [2*s['box_dbu'][0]-3*u, 2*s['box_dbu'][1]-3*u, 2*s['box_dbu'][2]+3*u, 2*s['box_dbu'][3]+3*u])]
        tnodes.append((t['instance']+'/'+t['pin'], hit))
    src = rep[pin_nodes[0]]
    keep = [i for i in range(n) if i != src]; pos = {k: i for i, k in enumerate(keep)}
    Gr = G[np.ix_(keep, keep)]
    Z = np.linalg.pinv(Gr)
    missing = [t for t, hit in tnodes if not hit]
    # Bound: whole net current drawn at the worst single terminal.
    reff = [min((Z[pos[h], pos[h]] if h in pos else 0.0) for h in hit) for _, hit in tnodes if hit]
    worst = max(reff, default=0.0)
    # Distributed: equal share at every terminal; branch currents for EM.
    inj = np.zeros(len(keep)); share = I/max(1, len(tnodes))
    for _, hit in tnodes:
        if hit and hit[0] in pos:
            inj[pos[hit[0]]] += share
    v = Z @ inj; volt = np.zeros(n); volt[keep] = v
    em = 0.0; em_at = None; cut_util = 0.0; cut_at = None; em125 = 0.0; em_top = []
    for (i, j), k in vcount.items():
        cur = abs((volt[i]-volt[j])*(-G[i, j]))
        if cur/k/CUT_LIMIT > cut_util:
            cut_util = cur/k/CUT_LIMIT
            cut_at = dict(current_per_cut_a=cur/k, cuts=k, layers=[metal[i][0], metal[j][0]],
                          boxes_um=[[c/u for c in metal[i][1]], [c/u for c in metal[j][1]]])
    for i in range(n):
        for j in range(n):
            if i != j and G[i, j] < 0 and (min(i, j), max(i, j)) not in vcount:
                cur = abs((volt[i]-volt[j])*(-G[i, j]))
                width = min(min(metal[k][1][2]-metal[k][1][0], metal[k][1][3]-metal[k][1][1])/u for k in (i, j))
                util = cur/width/J_LIMIT[metal[i][0]]
                if i < j and util > .25:
                    em_top.append(dict(util=round(util, 3), current_a=cur, width_um=width, layer=metal[i][0],
                                       boxes_um=[[c/u for c in metal[k][1]] for k in (i, j)]))
                em125 = max(em125, cur/width/J_125[metal[i][0]])
                if util > em:
                    em, em_at = util, dict(current_a=cur, width_um=width, layer=metal[i][0])
    dist_drop = float(volt.max())
    tv = [(t, max(volt[h] for h in hit)) for t, hit in tnodes if hit]
    worst_term = max(tv, key=lambda x: x[1], default=(None, 0))[0]
    drops = sorted(((abs(volt[i]-volt[j]), i, j) for i in range(n) for j in range(i+1, n) if G[i, j] < 0), reverse=True)[:8]
    drop_top = [dict(dv_v=float(d), layers=[metal[i][0], metal[j][0]], boxes_um=[[c/u for c in metal[k][1]] for k in (i, j)])
                for d, i, j in drops]
    passed = not missing and dist_drop <= IR_LIMIT and em <= 1 and cut_util <= 1
    ok &= passed
    out[name] = dict(status='pass' if passed else 'fail', assumed_current_a=I, terminals=len(tnodes), unreached=missing,
                     distributed_ir_drop_v=dist_drop, worst_terminal=worst_term, largest_branch_drops=drop_top, worst_single_terminal_bound_v=I*worst, worst_reff_ohm=worst,
                     em_max_utilisation=em, em_worst=em_at, em_top=sorted(em_top, key=lambda e: -e['util'])[:12], via_cut_max_utilisation=cut_util, via_cut_worst=cut_at,
                     info_125c=dict(em_max_utilisation=em125, via_cut_max_utilisation=cut_util*CUT_LIMIT/CUT_125),
                     rectangles=n, collapsed_contained_rectangles=collapsed, vias=len(cuts))
(work/'supply-ir.json').write_text(json.dumps(dict(status='pass' if ok else 'fail', ir_limit_v=IR_LIMIT, j_limit_a_per_um=J_LIMIT, cut_limit_a=CUT_LIMIT, j_125c=J_125, cut_125c_a=CUT_125,
                                                    net_currents_a=NET_A, source='https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html',
                                                    method=__doc__, nets=out), indent=2)+'\n')
print(json.dumps({k: (v['status'], round(v['distributed_ir_drop_v']*1e3, 3), round(v['worst_single_terminal_bound_v']*1e3, 3), round(v['em_max_utilisation'], 3), round(v['via_cut_max_utilisation'], 3), round(v['info_125c']['via_cut_max_utilisation'], 3), round(v['info_125c']['em_max_utilisation'], 3)) for k, v in out.items()}))
sys.exit(0 if ok else 1)
