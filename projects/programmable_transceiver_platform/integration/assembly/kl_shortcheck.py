# Stage `shortcheck` (tool image, KLayout python):  tool.sh <chip> python3 /asm/kl_shortcheck.py [drop-cell ...]
# Is VDD joined to VSS (or a signal to a supply) on the assembled chip, and by what? Extracts Metal1-5 + Via1-4 + Contact
# connectivity of chip/pt_chip_top.gds with the named top-level instances removed (e.g. pt_top_wiring = no router wiring),
# then probes one point of the VDD core ring and one of the VSS core ring (from the grid, place.json) and reports whether
# they are one net. Light on memory (flat region connectivity, merged).
import json, os, sys
import klayout.db as db
drop = set(sys.argv[1:])
ly = db.Layout(); ly.read('/run/chip/pt_chip_top.gds'); top = ly.cell('pt_chip_top')
for i in list(top.each_inst()):
    if i.cell.name in drop: i.delete()
L = lambda a, b: ly.find_layer(a, b)
names = [('M1', 34), ('V1', 35), ('M2', 36), ('V2', 38), ('M3', 42), ('V3', 40), ('M4', 46), ('V4', 41), ('M5', 81)]
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, []))
lay = {}
for n, g in names:
    li = L(g, 0)
    lay[n] = l2n.make_layer(li, n) if li is not None else l2n.make_layer(n)
for a, v, b in (('M1', 'V1', 'M2'), ('M2', 'V2', 'M3'), ('M3', 'V3', 'M4'), ('M4', 'V4', 'M5')):
    l2n.connect(lay[a]); l2n.connect(lay[v]); l2n.connect(lay[b]); l2n.connect(lay[a], lay[v]); l2n.connect(lay[v], lay[b])
l2n.extract_netlist()
nl = l2n.netlist(); nl.make_top_level_pins(); nl.purge()
man = json.load(open('/run/place.json'))
# probe points: the centres of grid strap pieces of each net (the hook slots, place.json), several per net
lmap = {'Metal4': 'M4', 'Metal5': 'M5'}
def nid(h):
    p = db.DPoint((h['piece'][0]+h['piece'][2])/2, (h['piece'][1]+h['piece'][3])/2)
    n = l2n.probe_net(lay[lmap[h['layer']]], p)
    return None if n is None else (n.circuit.name, n.cluster_id)
ids = {'VDD': set(), 'VSS': set()}
for h in man['hooks'][:400]:
    k = h['net'].split('__')[0]; v = nid(h)
    if v: ids[k].add(v)
out = dict(dropped=sorted(drop), vdd_nets=len(ids['VDD']), vss_nets=len(ids['VSS']), vdd_vss_one_net=bool(ids['VDD'] & ids['VSS']))
print(json.dumps(out))
json.dump(out, open('/run/shortcheck.json', 'w'))
