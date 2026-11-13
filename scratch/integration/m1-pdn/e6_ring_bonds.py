#!/usr/bin/env python3
"""E6: bond allocation and ring checks (static). (a) per-bond DC current vs the 60 mA native supply-cell rating
(power_budget.py NATIVE_CELL_MA); (b) AP4-10(b) core ring 2 x 25 um -> 2 x 12 um; (c) loss of one supply bond (open
bond: yield / bring-up robustness); (d) fraction of the rfdriver current that arrives through the RF_TX pad feed."""
import json, numpy as np
import model as M, core as C, loads as LD
res = {}
def run(tag, s, case, lv='evid+', **kw):
    over = kw.pop('over', {}); xf = kw.pop('x_feed', 0.0)
    p = M.pset(s); p.update(over); n, info, ports, vict = C.full(p, x_feed=xf, **kw)
    d = C.dc(n, info, case, lv, x_feed=xf)
    sb = {k: v for k, v in d['bond_mA'].items() if k in [x[0] for x in M.VDD_PADS]}; gb = {k: v for k, v in d['bond_mA'].items() if k not in sb}
    b = d['blocks']; worst = max(b.items(), key=lambda kv: (3.267-kv[1]['rail']) if kv[1].get('mA', 0) > 0.5 else 0)
    r = dict(I=d['total_mA'], ring_drop_max_mV=1e3*(3.267-d['ring_rail_min']), vdd_bond_max=(max(sb, key=sb.get), max(sb.values())),
             gnd_bond_max=(max(gb, key=gb.get), max(gb.values())), vdd_bonds=sb, gnd_bonds=gb, digital_drop_mV=1e3*(3.267-b['digital']['rail']),
             worst_block=(worst[0], 1e3*(3.267-worst[1]['rail'])))
    res[tag] = r
    print(f"{tag:58s} I {r['I']:5.0f}  ring drop max {r['ring_drop_max_mV']:5.1f} mV  VDD bond max {r['vdd_bond_max'][1]:4.0f} mA (pad {r['vdd_bond_max'][0]})  "
          f"GND bond max {r['gnd_bond_max'][1]:4.0f} mA (pad {r['gnd_bond_max'][0]})  digital {r['digital_drop_mV']:5.1f}  worst {worst[0]} {r['worst_block'][1]:5.0f}")
for s in ('opt', 'nom', 'pess'):
    for case in ('wired_external_clock', 'rf_tx_autonomous', 'usb'):
        for lv in ('alloc', 'evid+'):
            run(f'(a) {s} {case} {lv}', s, case, lv)
for s in ('nom', 'pess'):
    run(f'(b) {s} wired core ring 25 um', s, 'wired_external_clock')
    run(f'(b) {s} wired core ring 12 um (AP4-10b)', s, 'wired_external_clock', over=dict(core_ring_w=12.0))
    run(f'(b) {s} rf_tx core ring 12 um (AP4-10b)', s, 'rf_tx_autonomous', over=dict(core_ring_w=12.0))
# (c) one supply bond open: drop each in turn (nominal set, wired)
import copy
for drop in [x[0] for x in M.VDD_PADS]:
    keep = [x for x in M.VDD_PADS if x[0] != drop]; old = M.VDD_PADS
    M.VDD_PADS = keep; run(f'(c) nom wired, supply bond {drop} open', 'nom', 'wired_external_clock'); M.VDD_PADS = old
for xf in (0.0, 0.5, 0.8):
    run(f'(d) nom rf_tx_autonomous, rfdriver feed via pads x={xf}', 'nom', 'rf_tx_autonomous', x_feed=xf)
json.dump(res, open('out/e6_ring_bonds.json', 'w'), indent=0)
# (e) two extra supply/ground pairs on the edges that have none (south: D2H row, north: digital macro), from spare sites
old_v, old_g = M.VDD_PADS, M.VSS_PADS
M.VDD_PADS = old_v+[(2, 'X', 2.4), (40, 'X', 2.4)]; M.VSS_PADS = old_g+[(16, ), ][0:0]+[16, 52]
for s in ('nom', 'pess'):
    run(f'(e) {s} wired +VDD at pads 2,40 +GND at 16,52', s, 'wired_external_clock')
    run(f'(e) {s} rf_tx +VDD at pads 2,40 +GND at 16,52', s, 'rf_tx_autonomous')
M.VDD_PADS, M.VSS_PADS = old_v, old_g
json.dump(res, open('out/e6_ring_bonds.json', 'w'), indent=0)
