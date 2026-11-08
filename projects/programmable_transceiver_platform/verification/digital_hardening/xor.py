# KLayout batch XOR of two GDS files (a = analog-image Magic 8.3.678 export, b = LibreLane
# canary Magic 8.3.623 export). Writes per-layer XOR shape counts to $out.
import json
import klayout.db as db
la, lb = db.Layout(), db.Layout()
la.read(a); lb.read(b)
ta, tb = la.top_cell(), lb.top_cell()
res = {'top_a': ta.name, 'top_b': tb.name, 'layers': {}}
keys = set()
for L in (la, lb):
    for li in L.layer_indexes():
        i = L.get_info(li); keys.add((i.layer, i.datatype))
tot = 0
for (l, d) in sorted(keys):
    ra = db.Region(ta.begin_shapes_rec(la.layer(l, d))); ra.merge()
    rb = db.Region(tb.begin_shapes_rec(lb.layer(l, d))); rb.merge()
    x = ra ^ rb
    n = x.count()
    res['layers'][f'{l}/{d}'] = dict(a=ra.count(), b=rb.count(), xor=n)
    tot += n
res['xor_total'] = tot
json.dump(res, open(out, 'w'), indent=1)
print('XOR_TOTAL', tot)
