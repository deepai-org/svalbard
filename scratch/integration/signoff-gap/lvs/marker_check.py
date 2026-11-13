# klayout -b -r marker_check.py -rd jobs=/w/kljobs.txt : fill keep-out markers present per block GDS?
import klayout.db as db
hits = {}
for ln in open(jobs):
    name, gds = ln.split()[:2]
    ly = db.Layout(); ly.read(gds.replace('/home/ubuntu/svalbard', '/repo'))
    m = [f'{l}/{d}' for l, d in ((152, 5), (111, 5), (151, 5)) if ly.find_layer(l, d) is not None and any(not c.shapes(ly.find_layer(l, d)).is_empty() for c in ly.each_cell())]
    if m: hits[name] = m
print('blocks with PMNDMY/NDMY/IND_MK:', hits)
