#!/usr/bin/env python3
"""Die-fit of one chip: collect run/<chip>/fit-*.json and <chip>/overheads.json into the margin table.
    CHIP=rf|wired python3 summarize.py      -> <chip>/summary.json, markdown on stdout
Margin (mm2) of a packing = free core that can still take a >= 60 um block (scrap slivers excluded) minus the routing the
halo channels cannot carry at realistic pitch (control at minimum pitch, data / clock / analog at double pitch; overheads.py),
when that is positive. 'All placed' is required: an unplaced block is a negative margin of its area plus its halo."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); CHIP = os.environ['CHIP']
O = json.load(open(f'{HERE}/{CHIP}/overheads.json')) if os.path.exists(f'{HERE}/{CHIP}/overheads.json') else {}
rows = []
for t in ('s', 't', 'lb'):
    f = f'{HERE}/run/{CHIP}/fit-{t}.json'
    if not os.path.exists(f): continue
    r = json.load(open(f)); ro = O.get(f'routing_{t}', {})
    need = ro.get('channel_need_mm2', {}).get('control_min_fast_double'); cap = ro.get('channel_area_mm2')
    short = round(max(0.0, need - cap), 2) if need is not None and cap is not None else None
    m = r['free_usable_80um_mm2'] - (short or 0.0) - (r['unplaced_mm2']*1.25 if r['unplaced'] else 0.0)
    rows.append(dict(tag=t, scenario=r['scenario'], macro=f"{r['macro']['w']:.0f} x {r['macro']['h']:.0f}", core=r['core_mm2'],
                     blocks=r['blocks'], demand=r['block_demand_mm2'], placed=r['placed'], unplaced=len(r['unplaced']), unplaced_mm2=r['unplaced_mm2'],
                     channels=r['halo_area_mm2'], free=r['free_after_mm2'], usable60=r['free_usable_80um_mm2'], scrap=r['scrap_lt80um_mm2'],
                     relaxed=[x[0] for x in r['relaxed']], rule_fails=[(x['aggressor'], x['victim'], x['gap_um']) for x in r['rule_fails']],
                     channel_need_realistic=need, channel_area=cap, routing_short=short, margin=round(m, 2)))
json.dump(dict(chip=CHIP, rows=rows), open(f'{HERE}/{CHIP}/summary.json', 'w'), indent=1)
print(f'pt_{CHIP}')
print('| scenario | macro um | blocks to place mm2 | placed / unplaced (mm2) | channels (halo) | free | usable >= 60 um | scrap | routing beyond channels | **margin** | relaxed | rule fails |')
print('|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|')
for x in rows:
    print(f"| {x['scenario']} | {x['macro']} | {x['demand']} | {x['placed']} / {x['unplaced']} ({x['unplaced_mm2']}) | {x['channels']} | {x['free']} | {x['usable60']} | "
          f"{x['scrap']} | {x['routing_short'] if x['routing_short'] is not None else '?'} | **{x['margin']:+.2f}** | {', '.join(x['relaxed']) or '-'} | {len(x['rule_fails'])} |")
