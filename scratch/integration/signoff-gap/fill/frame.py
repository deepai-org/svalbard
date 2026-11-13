# klayout -b -r frame.py -rd gds=in.gds -rd out=framed.gds [-rd topname=...] [-rd margin=26]
# Block-level fill needs the block inside a frame: the PDK fill script keeps 26 um clear of the layout bbox ("scribe line").
# New top FRAME_<top> = block instance + a 0/0 boundary box grown by the margin. The block itself is untouched.
import klayout.db as db
ly = db.Layout(); ly.read(gds)
tn = globals().get('topname')
blk = ly.cell(tn) if tn else max(ly.top_cells(), key=lambda c: c.bbox().area())
m = int(float(globals().get('margin', 26)) / ly.dbu)
# drop other top cells so the fill script's single top_cell works
for c in [c for c in ly.top_cells() if c.cell_index() != blk.cell_index()]:
    c.prune_cell()
f = ly.create_cell('FRAME_' + blk.name)
f.insert(db.CellInstArray(blk.cell_index(), db.Trans()))
f.shapes(ly.layer(0, 0)).insert(blk.bbox().enlarged(m, m))
ly.write(out)
print(f.name, blk.bbox())
