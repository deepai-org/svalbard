"""Independent derivation of site -> bond finger from coordinates only (no site-order list):
for each die orientation, the sites of each die edge are paired by rank with the fingers of the board
row facing that edge (the only assignment without crossing wires; die pitch 0.18/0.211 mm fans out to
0.4 mm fingers, so each site takes the finger of its rank).  Exactly one orientation puts every ground
site on a GND finger and every supply site on a supply finger.  python only."""
import json, math
R = '/home/ubuntu/svalbard/'
P = R + 'projects/programmable_transceiver_platform/'
sites = json.load(open(P + 'analog/pads/generated/provider-sites.json'))
d = json.load(open(R + 'scratch/cob/raw.json'))
U = [f for f in d['footprints'] if f['ref'] == 'U102'][0]
fing = {int(q['num']): (q['at'], q['net']) for q in U['pads'] if q['num'].isdigit() and int(q['num']) <= 74}
x0, y0, x1, y1 = sites['die_area_um']
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
S = {k: ((v['bond_center_um'][0] - cx) / 1e3, (v['bond_center_um'][1] - cy) / 1e3) for k, v in sites['sites'].items()}
T = {'I': (1, 0, 0, 1), 'R180': (-1, 0, 0, -1), 'MX(x->-x)': (-1, 0, 0, 1), 'MY(y->-y)': (1, 0, 0, -1)}  # 90-deg ones do not fit a 3.9x5.1 die
def edge(p, hx, hy):
    x, y = p
    return ('S' if y < 0 else 'N') if hy - abs(y) < hx - abs(x) else ('W' if x < 0 else 'E')
def tang(e, p): return p[0] if e in 'SN' else p[1]
def assign(a, b, c, e):
    pts = {s: (a * x + b * y, c * x + e * y) for s, (x, y) in S.items()}
    m = {}
    for ed in 'SNWE':
        ss = sorted((s for s, p in pts.items() if edge(p, (x1 - x0) / 2e3, (y1 - y0) / 2e3) == ed), key=lambda s: tang(ed, pts[s]))
        ff = sorted((n for n, (p, _) in fing.items() if edge(p, 4.3, 4.7) == ed), key=lambda n: tang(ed, fing[n][0]))
        assert len(ss) == len(ff), (ed, len(ss), len(ff))
        m.update(zip(ss, ff))
    return m
def kind(net): return 'gnd' if net == 'GND' else ('sig' if net.startswith('/') else 'sup')
def skind(s): return 'gnd' if s.startswith(('dvss', 'vss')) else ('sup' if s.startswith(('dvdd', 'vdd')) else 'sig')
res = {}
for name, (a, b, c, e) in T.items():
    m = assign(a, b, c, e)
    bad = [s for s, n in m.items() if kind(fing[n][1]) != skind(s)]
    res[name] = (m, bad)
    print(name, 'net-class mismatches:', len(bad), 'distinct fingers:', len(set(m.values())), 'clk_pad ->', m['clk_pad'])
ok = [k for k, (m, bad) in res.items() if not bad and len(set(m.values())) == 74]
assert len(ok) == 1, ok
m = res[ok[0]][0]
json.dump(dict(transform=ok[0], site_to_bond=m), open('site_to_bond.json', 'w'), indent=1)
c = json.load(open(P + 'spec/contract.json'))['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
old = c['south'] + c['east'] + c['north'] + list(reversed(c['west']))
new = c['south'] + c['east'] + list(reversed(c['north'])) + list(reversed(c['west']))
print('unique orientation:', ok[0])
print('old expression wrong sites:', sorted(m[s] for i, s in enumerate(old) if m[s] != i + 1))
print('new expression wrong sites:', [s for i, s in enumerate(new) if m[s] != i + 1])
ba = json.load(open(R + 'scratch/pads-core/bond/bond-audit.json'))
print('bond-audit.json keys', list(ba)[:8] if isinstance(ba, dict) else type(ba))
for s in c['north']: print(' north', s, 'bond', m[s], fing[m[s]][1], 'chip x um', sites['sites'][s]['bond_center_um'][0])
