"""Merge bond-wire.json into a package-channel.json. Adds only: pins[*].bond_wire, supplies_grounds[*].bond_wire and the
top-level key bond_wire_assumptions; no existing key is changed.
usage: python3 -I merge_bond_wire.py <package-channel.json in> <bond-wire.json> <out.json>"""
import json, sys
src, bw, dst = sys.argv[1:4]
pc = json.load(open(src)); w = json.load(open(bw)); B = w['bonds']
def frag(b):
    e = B[str(b)]
    return dict(plan_mm_centre=e['plan_mm']['C'], plan_mm_near_end=e['plan_mm']['N'], angle_deg_centre=e['angle_deg']['C'], angle_deg_near_end=e['angle_deg']['N'],
                length_3d_mm={k: e['length_3d_mm'][k] for k in ('min', 'nom', 'max')}, L_nH=e['L_nH'], R_mohm_Al=e['R_mohm_Al'], R_mohm_Au=e['R_mohm_Au'])
n = 0
for sec in ('pins', 'supplies_grounds'):
    for name, p in pc[sec].items():
        b = p['bond_pad']; assert str(b) in B, (name, b)
        site = name if sec == 'supplies_grounds' else p['site']
        assert site.replace('.pad', '') == B[str(b)]['site'], (name, site, B[str(b)]['site'])
        p['bond_wire'] = frag(b); n += 1
assert n == 74, n
pc['bond_wire_assumptions'] = dict(w['wire_assumptions'], current=w['current'], source='scratch/pads-core/ws/bond-wire.json (wire.py), ' + w['status'])
json.dump(pc, open(dst, 'w'), indent=1)
print('merged', n, 'bonds ->', dst)
