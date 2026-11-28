"""Dummy COMP (22/4) for pt_wiredtx8 (coordinator 2026-11-28, precheck DCF.1a): KLayout python, assembly image.
    python3 dummy_comp.py <in.gds> <out.gds> <cell> <x0> <y0> <x1> <y1> [size] [space]
Fills the zone (block um) with squares where the shuttle deck's dummy-COMP rules allow them: DCF.4 3.5 to COMP, DCF.5 1.5
to Poly2, DCF.6a-d 1.3 / 4 / 1.3 / 1.3 to the Nwell / DNWELL / LVPWELL / Dualgate boundaries, DCF.8a 3.5 to RES_MK, DCF.11a
3.5 to NDMY, DCF.12 3 to IND_MK, DCF.2b 1.9 between dummies. Floating (no contact, no implant), as the PDK fill draws them.
Writes the GDS with the dummies in a child cell <cell>_dcomp and prints the count and the zone's COMP + dummy share."""
import sys, json
try:
    import klayout.db as db
    A = sys.argv[1:]
except ImportError:                       # inside `klayout -b -r` (analog image): arguments as -rd a=...
    import pya as db
    A = [globals()[k] for k in ('inp', 'out', 'cell', 'zone', 'ndmy')]
    A = A[:3] + A[3].split(',') + [A[4]]
inp, out, cell = A[0:3]; z = [float(v) for v in A[3:7]]
NDMY_SPEC = A[7] if len(A) > 7 else ''   # "x0,x1,width,gap,y0,y1": fixed NDMY tile grid, block-local um
S, SP = 2.0, 1.9
ly = db.Layout(); ly.read(inp); top = ly.cell(cell); um = lambda v: int(round(v / ly.dbu))
# NDMY (111/5) tiles over the COMP-free ser8d poly bands (coordinator 2026-11-28, DCF.1a exception): a fixed grid, exactly
# 20.000 um gaps (DE.4 >= 20), tiles <= 14000 um2 (DE.3 15000 with margin), >= 0.8 um wide (DE.2); asserted below
NDMY = db.Region()
if NDMY_SPEC:
    x0, x1, tw, tg, y0, y1 = [float(v) for v in NDMY_SPEC.split(':')]
    x = x0
    while x < x1 - 1e-6:
        NDMY.insert(db.Box(um(x), um(y0), um(min(x + tw, x1)), um(y1))); x += tw + tg
    for p in NDMY.each():
        b = p.bbox(); a = b.width() * b.height() * ly.dbu * ly.dbu
        assert min(b.width(), b.height()) * ly.dbu >= 0.8, 'DE.2'
        assert a <= 14000.0, f'DE.3 margin: tile {a:.0f} um2'
    sp = NDMY.space_check(um(20)) if hasattr(NDMY, 'space_check') else NDMY.space(um(20))
    assert sp.is_empty(), 'DE.4: NDMY tiles closer than 20 um'
    top.shapes(ly.layer(111, 5)).insert(NDMY)
    print(f'NDMY {NDMY.count()} tiles, {NDMY.area()*ly.dbu*ly.dbu:.0f} um2')
def R(l, d=0):
    li = ly.find_layer(l, d); return db.Region(top.begin_shapes_rec(li)).merged() if li is not None else db.Region()
ring = lambda r, d: (r.sized(um(d)) - r.sized(-um(d))) if not r.is_empty() else db.Region()
zone = db.Region(db.Box(um(z[0]), um(z[1]), um(z[2]), um(z[3])))
bad = (R(22).sized(um(3.5)) + R(30).sized(um(1.5)) + ring(R(21), 1.3) + ring(R(12), 4.0) + ring(R(204), 1.3) + ring(R(55), 1.3)
       + R(110, 5).sized(um(3.5)) + (R(111, 5) + NDMY).sized(um(3.5)) + R(151, 5).sized(um(3.0)) + R(22, 4).sized(um(SP)))
legal = (zone.sized(-um(1.0)) - bad).merged()
fit = legal.sized(-um(S / 2))          # centres where a square fits
dc = ly.create_cell(cell + '_dcomp'); L = ly.layer(22, 4); n = 0
P = um(S + SP); b = zone.bbox()
for x in range(b.left, b.right, P):
    for y in range(b.bottom, b.top, P):
        c = db.Point(x + um(S / 2), y + um(S / 2))
        if fit.interacting(db.Region(db.Box(c, c).enlarged(1, 1))).is_empty(): continue
        dc.shapes(L).insert(db.Box(x, y, x + um(S), y + um(S))); n += 1
top.insert(db.CellInstArray(dc.cell_index(), db.Trans()))
dens = (R(22) + db.Region(dc.begin_shapes_rec(L))).merged() & zone
print(f'dummy COMP {n} squares {S} um, zone COMP+dummy {100*dens.area()/zone.area():.1f} %')
# DCF.1a-style residual in the zone: area with no COMP / dummy that survives a 10 um shrink-grow
res = ((zone - (R(22) + db.Region(dc.begin_shapes_rec(L))) - NDMY).merged().sized(-um(10)).sized(um(10))) & zone
print('residual 20x20 empty windows', res.count(), [str(p.bbox()) for p in res.each()][:10])
ly.write(out)
