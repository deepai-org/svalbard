"""Custom pad finalizer: makes every custom pad cell correct by construction for wedge bonding (MANDATE 2, GF180 CUP.1a)
and for the provider ring it sits in (risk PAD-16). Applied to every custom pad family when it is imported
(kl_abstract.import_cell / abstract), and standalone to write the finalized pad GDS for pad DRC / LVS / the CUP gate:

  python3 pad_cup.py <in.gds> <out.gds> [cell]          (KLayout python module klayout.db, or klayout -b -r with -rd)

Rules applied to each pad opening (Pad 37/0):
  1. Under the opening only the stock Bondpad_5LM stack: every instance that reaches into the opening and is not
     Bondpad_5LM is flattened into the pad cell, then every shape of every layer except Pad is cut out of the opening;
     the Bondpad_5LM instance (its Metal2-5 plates, Via2-4 arrays of 0.26 um cuts) is kept unchanged. Generator straps
     that ran into the plate's notches (every family: 4.8-52.5 um2 of Metal2) end at the opening edge and still join
     the plate outside it.
  2. Provider-ring rail band: no pad Via3 / Via4 in pad-local y in RING_BAND (the retained_provider_ring rail stack,
     identical in the frame of every custom-pad site on both chips: 70.000-348.390 um, measured on fpw-14 / pt_wired).
     The ring's own Via3 / Via4 arrays join the rails; pad cuts there were off its lattice (PAD-16: V3.1/V3.2a/V4.1/V4.2a
     ~1870 on fpw-14). The pad's metal in the band overlaps the ring's same-net rail metal on every layer.
Returns / prints what was removed so a change in a generator shows up."""
import sys
try:
    import klayout.db as db
except ImportError:
    import pya as db

PAD = (37, 0)
RING_BAND = (69.5, 348.9)       # um, pad-local; 0.5 um beyond the ring's rail metal (70.000-348.390)
BAND_VIAS = [(40, 0), (41, 0)]  # Via3, Via4
BOND = 'Bondpad_5LM'
REF_GDS = '/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds'   # in both tool images
STACK = [(36, 0), (38, 0), (42, 0), (40, 0), (46, 0), (41, 0), (81, 0)]           # Metal2, Via2, Metal3, Via3, Metal4, Via4, Metal5
_REF = {}


def ref_stack(dbu, path=None):
    """the stock Bondpad_5LM stack under its opening, centred on the opening: {layer: Region}"""
    if _REF: return _REF
    rl = db.Layout(); rl.read(path or REF_GDS); rc = rl.cell(BOND)
    assert abs(rl.dbu - dbu) < 1e-12
    op = db.Region(rc.begin_shapes_rec(rl.find_layer(*PAD))).merged(); c = op.bbox().center()
    for L in STACK:
        li = rl.find_layer(*L)
        _REF[L] = (db.Region(rc.begin_shapes_rec(li)).merged() & op).moved(-c.x, -c.y)
    _REF['op'] = op.moved(-c.x, -c.y)
    return _REF


def _is_bond(c): return c.name.split('$')[0].endswith(BOND)      # Magic / assembly prefix it (pad_rf_pair__svrfpad__Bondpad_5LM)


def finalize(ly, cell, ref=None):
    um = lambda v: int(round(v / ly.dbu))
    R = ref_stack(ly.dbu, ref)
    tops0 = {t.cell_index() for t in ly.top_cells()}
    pli = ly.find_layer(*PAD)
    rep = dict(openings=0, flattened=0, cut_um2={}, band_vias=0)
    if pli is not None:
        ops = db.Region(cell.begin_shapes_rec(pli)).merged()
        rep['openings'] = ops.count()
        for _ in range(8):      # flatten until no non-bond instance reaches an opening
            hit = [i for i in cell.each_inst() if not _is_bond(i.cell) and not ops.interacting(db.Region(i.bbox())).is_empty()
                   and any(not db.Region(i.cell.begin_shapes_rec(li)).transformed(i.cplx_trans).interacting(ops).is_empty()
                           for li in ly.layer_indexes() if li != pli)]
            if not hit: break
            for i in hit: i.flatten(1); rep['flattened'] += 1
        # orientation of the stack each opening carries now (best Via2 match of the 8), to put the stock stack back alike
        v2 = ly.find_layer(38, 0); orient = []
        for p in ops.each():
            pr = db.Region(p); c = pr.bbox().center()
            assert (pr ^ R['op'].moved(c.x, c.y)).is_empty(), f'opening {pr.bbox()} is not the 60 x 60 um Bondpad_5LM opening'
            cur = (db.Region(cell.begin_shapes_rec(v2)) & pr) if v2 is not None else db.Region()
            best = min((db.ICplxTrans(1, a, m, c.x, c.y) for m in (False, True) for a in (0, 90, 180, 270)),
                       key=lambda t: (R[(38, 0)].transformed(t) ^ cur).area())
            orient.append(best)
        for li in ly.layer_indexes():
            if li == pli: continue
            sh = cell.shapes(li)
            if sh.is_empty(): continue
            r = db.Region(sh); cut = (r & ops)
            if cut.is_empty(): continue
            info = ly.get_info(li); rep['cut_um2'][f'{info.layer}/{info.datatype}'] = round(cut.area() * ly.dbu ** 2, 2)
            keep = r - ops
            # text / label shapes are not polygons: keep the non-polygon shapes as they are
            texts = [s.text for s in sh.each() if s.is_text()]
            sh.clear(); sh.insert(keep)
            for t in texts: sh.insert(t)
        for t in orient:          # the stock stack, exactly, under each opening
            for L in STACK: cell.shapes(ly.layer(*L)).insert(R[L].transformed(t))
    band = db.Region(db.Box(-um(1e5), um(RING_BAND[0]), um(1e5), um(RING_BAND[1])))
    for L in BAND_VIAS:
        li = ly.find_layer(*L)
        if li is None: continue
        # cuts may sit in sub-cells (via arrays): flatten instances that put cuts into the band first
        for _ in range(8):
            hit = [i for i in cell.each_inst() if not _is_bond(i.cell) and not band.interacting(db.Region(i.bbox())).is_empty()
                   and not db.Region(i.cell.begin_shapes_rec(li)).transformed(i.cplx_trans).interacting(band).is_empty()]
            if not hit: break
            for i in hit: i.flatten(1); rep['flattened'] += 1
        sh = cell.shapes(li); r = db.Region(sh); inb = r.interacting(band)
        if inb.is_empty(): continue
        rep['band_vias'] += inb.count()
        sh.clear(); sh.insert(r - inb)
    for t in [t for t in ly.top_cells() if t.cell_index() not in tops0]: t.prune_cell()    # cells orphaned by flattening
    return rep


if __name__ == '__main__' or 'inp' in globals():
    g = globals()
    a = [g['inp'], g['out'], g.get('cell')] if 'inp' in g else (sys.argv[1:] + [None])[:3]
    ly = db.Layout(); ly.read(a[0])
    c = ly.cell(a[2]) if a[2] else sorted(ly.top_cells(), key=lambda t: -t.bbox().area())[0]
    print(c.name, finalize(ly, c))
    ly.write(a[1])
