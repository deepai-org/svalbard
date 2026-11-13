# Negative-control GDS variants. usage: python3 nc_make.py in.gds outdir
import klayout.db as db, sys, os
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
def variant(name, fn):
    ly = db.Layout(); ly.read(src); n = fn(ly); ly.write(f'{out}/{name}.gds'); print(name, 'shapes removed:', n)
def drop_layer(l, d):
    def f(ly):
        i = ly.find_layer(l, d); n = 0
        if i is None: return 0
        for c in ly.each_cell():
            n += c.shapes(i).size(); c.shapes(i).clear()
        return n
    return f
def drop_one(l, d):
    def f(ly):
        i = ly.find_layer(l, d)
        top = max(ly.top_cells(), key=lambda c: c.bbox().area())
        for s in top.shapes(i).each():
            s.delete(); return 1
        return 0
    return f
variant('nc_no_hres', drop_layer(62, 0))        # INT-19 class: HRES marker dropped -> 1k poly becomes plain poly
variant('nc_no_via2_one', drop_one(38, 0))      # one top-level Via2 removed -> open
variant('nc_no_via1_one', drop_one(35, 0))
variant('nc_no_resmk', drop_layer(110, 5))
