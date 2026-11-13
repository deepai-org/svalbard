# klayout -b -r remap.py -rd gds=<block>.fill.gds -rd out=<block>.fillm.gds -rd nofill=<block>.nofill.gds
# For parasitic extraction WITH fill: Magic's gf180mcuD tech maps dummy metal (x/4) to fillmN types that are not
# conductors in the extract section, so stock PEX ignores fill. Here dummy Metal1-5 and dummy Poly2 are moved to the
# drawing datatype (x/0) as floating shapes, flattened into the FRAME top. Dummy COMP (22/4) is dropped (substrate-side
# only; not modelled). The no-fill twin is the same FRAME top with every dummy shape removed.
import klayout.db as db
MAP = {(34, 4): (34, 0), (36, 4): (36, 0), (42, 4): (42, 0), (46, 4): (46, 0), (81, 4): (81, 0), (30, 4): (30, 0)}
def build(with_fill, path):
    ly = db.Layout(); ly.read(gds)
    top = max(ly.top_cells(), key=lambda c: c.bbox().area())
    n = 0
    for (l, d), tgt in list(MAP.items()) + [((22, 4), None)]:
        i = ly.find_layer(l, d)
        if i is None: continue
        r = db.Region(top.begin_shapes_rec(i)); r.merge(); cnt = r.count()
        for c in ly.each_cell(): c.shapes(i).clear()
        if with_fill and tgt is not None:
            top.shapes(ly.layer(*tgt)).insert(r); n += cnt
    for c in [c for c in ly.each_cell() if c.name.upper().endswith(('_FILL', '_FILL_CELL'))]:
        c.prune_cell()
    ly.write(path); print(path, 'fill shapes kept', n)
build(True, out); build(False, nofill)
