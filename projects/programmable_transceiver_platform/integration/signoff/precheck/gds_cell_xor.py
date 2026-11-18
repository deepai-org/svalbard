# KLayout batch script: cell-by-cell geometric comparison of two GDS libraries (file hashes differ by timestamps).
#   klayout -b -zz -r gds_cell_xor.py -rd a=<old.gds> -rd b=<new.gds> -rd out=<json> [-rd cells=<file with names>]
# Per cell present in both: XOR of the cell's own shapes per layer (merged regions), text labels, and the instance
# list (child name, transformation, array). If the instance lists differ, a flat XOR of the whole cell decides.
# Equal own shapes + equal instances for every cell implies the flattened layouts are equal.
import pya, json
A = pya.Layout(); A.read(a)
B = pya.Layout(); B.read(b)
assert A.dbu == B.dbu
na = {c.name for c in A.each_cell()}; nb = {c.name for c in B.each_cell()}
want = None
try: want = {l.strip() for l in open(cells) if l.strip()}
except NameError: pass
linfo = sorted({(li.layer, li.datatype) for L in (A, B) for li in L.layer_infos()})
def insts(c):
    return sorted((i.cell.name, str(i.cell_inst.trans if not i.is_complex() else i.cell_inst.cplx_trans), i.na, i.nb, str(i.a), str(i.b)) for i in c.each_inst())
def texts(L, c):
    return sorted((li.layer, li.datatype, s.text.string, str(s.text.trans)) for li in L.layer_infos() for s in c.shapes(L.layer(li)).each(pya.Shapes.STexts))
res = {'a': a, 'b': b, 'cells_a': len(na), 'cells_b': len(nb), 'only_a': sorted(na - nb), 'only_b': sorted(nb - na), 'diff': {}, 'same': 0}
for n in sorted(na & nb):
    ca, cb = A.cell(n), B.cell(n); d = {}
    same_inst = insts(ca) == insts(cb)
    for (l, dt) in linfo:
        la, lb = A.find_layer(l, dt), B.find_layer(l, dt)
        if same_inst:
            ra = pya.Region(ca.shapes(la)) if la is not None else pya.Region()
            rb = pya.Region(cb.shapes(lb)) if lb is not None else pya.Region()
        else:
            ra = pya.Region(ca.begin_shapes_rec(la)) if la is not None else pya.Region()
            rb = pya.Region(cb.begin_shapes_rec(lb)) if lb is not None else pya.Region()
        x = ra ^ rb
        if not x.is_empty(): d['%d/%d' % (l, dt)] = {'xor_polygons': x.count(), 'xor_area_um2': x.area() * A.dbu * A.dbu, 'bbox': str(x.bbox())}
    if not same_inst: d['_instances'] = 'differ (flat XOR used)'
    if texts(A, ca) != texts(B, cb): d['_texts'] = 'differ'
    if ca.dbbox() != cb.dbbox(): d['_bbox'] = [str(ca.dbbox()), str(cb.dbbox())]
    if d: res['diff'][n] = d
    else: res['same'] += 1
if want is not None:
    res['wanted'] = {n: ('missing' if n not in (na & nb) else ('DIFF' if n in res['diff'] else 'same')) for n in sorted(want)}
json.dump(res, open(out, 'w'), indent=1)
print('cells a/b', len(na), len(nb), 'same', res['same'], 'diff', len(res['diff']), 'only_a', len(res['only_a']), 'only_b', len(res['only_b']))
