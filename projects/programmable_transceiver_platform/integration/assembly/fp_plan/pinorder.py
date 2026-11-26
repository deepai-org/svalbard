"""pinorder.py <eval.json> <chip.json> <out.cfg>: macro pin-order file (OpenLane pin_order.cfg style) from the planned pins"""
import json, sys, collections
E_ = json.load(open(sys.argv[1])); D = json.load(open(sys.argv[2])); out = sys.argv[3]
port = {}
for n, v in D['nets'].items():
    for e in v['ends']:
        if e[0] == 'digital': port.setdefault(n, []).append(e[1])
side = collections.defaultdict(list)
for n, (s, x, y) in E_['mpins'].items():
    for p in port.get(n, []): side[s].append((x if s in 'NS' else y, p, n))
r = E_['rect']['digital']
L = ['# Planned macro pin sides and order (FLOORPLAN_PLAN.md). Each pin faces the centroid of the other ends of its net.',
     f'# Macro outline in the plan: x {r[0]:.1f}-{r[2]:.1f}, y {r[1]:.1f}-{r[3]:.1f} um (die). Order: N/S left to right (increasing x),',
     '# E/W bottom to top (increasing y). The number after each name is the planned offset along the edge from the macro',
     '# lower-left corner (um); hardening may keep the order and spread the pins, 2.24 um minimum pitch.']
for s in 'NSEW':
    L.append(f'#{s}')
    for pos, p, n in sorted(side[s]):
        L.append(f'{p}  {pos - (r[0] if s in "NS" else r[1]):.1f}')
open(out, 'w').write('\n'.join(L) + '\n')
print({s: len(v) for s, v in side.items()}, 'ports', sum(len(v) for v in side.values()))
