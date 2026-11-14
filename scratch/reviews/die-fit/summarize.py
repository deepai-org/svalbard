#!/usr/bin/env python3
"""Die-fit: collect run/fit-*.json into one table (markdown on stdout, summary.json)."""
import json, glob, os
HERE = os.path.dirname(os.path.abspath(__file__)); rows = []
ORDER = ['b', 'c', 'cr', 'b-flow', 'c-flow', 'b-h5', 'c-h5', 'c-l1', 'c-l2', 'c-l3', 'c-l4', 'c-l5', 'c-l5-flow', 'cr-l5', 'b-l5', 'b-g500', 'b-g700', 'b-g900', 'b-g1100']
for t in ORDER:
    f = f'{HERE}/run/fit-{t}.json'
    if not os.path.exists(f): continue
    r = json.load(open(f)); tr = r['trials']
    by = {s: [x['unplaced_mm2'] for x in tr if x['strategy'] == s] for s in (0, 1, 2)}
    opts = []
    if r['halo_um'] != 10: opts.append(f"halo {r['halo_um']:.0f}")
    if r['nopad']: opts.append('debug pads on provider cells')
    if not r['bank']: opts.append('no bank')
    if r['ring_um']: opts.append(f"ring +{r['ring_um']:.0f}")
    if r['dropped']: opts.append('OPEN/SHORT frames out')
    if r['grow_um']: opts.append(f"die +{r['grow_um']:.0f} um tall")
    if all(x['strategy'] == 2 for x in tr): opts.append('flow-first order only')
    rows.append(dict(tag=t, scen=r['scenario'], opts=', '.join(opts) or 'baseline', core=r['core_mm2'], blocks=r['blocks'], demand=r['block_demand_mm2'],
                     placed=r['placed'], placed_mm2=r['placed_mm2'], unplaced=len(r['unplaced']), unplaced_mm2=r['unplaced_mm2'], halo=r['halo_area_mm2'],
                     free=r['free_after_mm2'], use80=r['free_usable_80um_mm2'], use200=r['free_usable_200um_mm2'], scrap=r['scrap_lt80um_mm2'],
                     relaxed=[x[0] for x in r['relaxed']], rule_fails=len(r['rule_fails']), macro=f"{r['macro']['w']:.0f} x {r['macro']['h']:.0f}",
                     trials=len(tr), best_by_strategy={s: (min(v) if v else None) for s, v in by.items()}, strap=r['strap_m5_area_mm2'],
                     biggest_unplaced=[(u[0], round(u[2]/1e6, 3)) for u in sorted(r['unplaced'], key=lambda u: -u[2])[:8]]))
json.dump(rows, open(f'{HERE}/summary.json', 'w'), indent=1)
print('| run | scenario | options | core | blocks to place mm2 | placed | unplaced n / mm2 | channels (halo) | free left | of it usable >= 60 um | relaxed | macro | trials |')
print('|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|')
for x in rows:
    print(f"| {x['tag']} | {x['scen']} | {x['opts']} | {x['core']} | {x['demand']} | {x['placed']} / {x['placed_mm2']} | {x['unplaced']} / **{x['unplaced_mm2']}** | {x['halo']} | {x['free']} | {x['use80']} | {', '.join(x['relaxed']) or '-'} | {x['macro']} | {x['trials']} |")
print()
for x in rows:
    print(x['tag'], 'best unplaced by ordering strategy (area / giants+flow / flow):', x['best_by_strategy'], '| biggest unplaced:', x['biggest_unplaced'][:6])
