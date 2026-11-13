# klayout -b -r keepout.py -rd gds=top.gds -rd out=top_ko.oas -rd pat='^pt_' [-rd grow=0] [-rd list=1]
# Adds fill keep-out markers (PMNDMY 152/5 for metal fill, NDMY 111/5 for COMP/Poly2 fill) over the bbox of every
# instance (any depth <= 3) whose cell name matches pat. Works on a copy; nothing else is changed.
import klayout.db as db, re, json
ly = db.Layout(); ly.read(gds)
top = max(ly.top_cells(), key=lambda c: c.bbox().area())
if globals().get('list'):
    print(sorted(set(i.cell.name for i in top.each_inst()))); raise SystemExit
rx = re.compile(pat); g = int(float(globals().get('grow', 0)) / ly.dbu)
reg = db.Region(); names = {}
def walk(cell, tr, d=0):
    for inst in cell.each_inst():
        t = tr * inst.cplx_trans
        if rx.search(inst.cell.name):
            reg.insert(inst.cell.bbox().transformed(t).enlarged(g, g)); names[inst.cell.name] = names.get(inst.cell.name, 0) + 1
        elif d < 3:
            walk(inst.cell, t, d + 1)
walk(top, db.ICplxTrans()); reg.merge()
for l in ((152, 5), (111, 5)):
    top.shapes(ly.layer(*l)).insert(reg)
ly.write(out)
print(json.dumps(dict(keepout_mm2=round(reg.area() * ly.dbu * ly.dbu / 1e6, 3), die_mm2=round(top.bbox().area() * ly.dbu * ly.dbu / 1e6, 3), cells=names)))
