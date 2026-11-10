"""Merge same-layer implant/marker shapes closer than their KLayout spacing rule.

The Magic gf180mcu PCells (guarded ppolyf resistors, hres snakes) leave sub-rule gaps between
same-type implant and marker shapes of one device and its guard ring: PPLUS 0.2 um apart (PP.2,
0.40), Dualgate and SAB rings 0.06/0.14 um from the device's own shape (DV.2 0.44, SB.2 0.42;
the deck text for DV.2 says "Merge if Space is less than this design rule").  Magic DRC does not
check these marker spacings; the tapeout precheck (KLayout) does.

merge(layout, cell) fills each such gap (morphological closing per layer) only where the fill
lies on field: it must not touch COMP, Poly2 or contacts, or the opposite implant.  It adds
shapes to `cell` and returns a per-layer report; it never removes geometry.  Run it inside the
pinned image (klayout.db) just before the final GDS write.
"""

# layer: (spacing rule um, layers the fill must not touch)
RULES = {
    (31, 0): (0.40, [(32, 0), (22, 0), (30, 0)]),   # PPLUS  PP.2; not NPLUS, COMP, Poly2
    (32, 0): (0.40, [(31, 0), (22, 0), (30, 0)]),   # NPLUS  NP.2
    (55, 0): (0.44, [(22, 0), (30, 0)]),            # Dualgate DV.2
    (49, 0): (0.42, [(22, 0), (30, 0), (33, 0)]),   # SAB    SB.2
}


def merge(layout, cell, rules=RULES):
    try:
        import klayout.db as k
    except ImportError:
        import pya as k
    dbu = layout.dbu
    report = {}
    for (ln, dt), (rule, forbid) in rules.items():
        li = layout.find_layer(ln, dt)
        if li is None:
            continue
        reg = k.Region(cell.begin_shapes_rec(li)).merged()
        if reg.is_empty():
            continue
        viol = reg.space_check(int(round(rule / dbu)))
        if viol.is_empty():
            continue
        d = int(round(rule / 2 / dbu)) + 1
        closed = reg.sized(d, d, 5).sized(-d, -d, 5)
        fill = (closed - reg).merged()
        # keep only pieces that sit in a reported gap
        fill = fill.interacting(viol.polygons(1))
        bad = k.Region()
        for fl in forbid:
            fi = layout.find_layer(*fl)
            if fi is not None:
                bad += k.Region(cell.begin_shapes_rec(fi))
        bad.merge()
        rejected = fill.interacting(bad)
        fill = fill.not_interacting(bad)
        cell.shapes(li).insert(fill)
        report[f'{ln}/{dt}'] = dict(rule_um=rule, gaps=viol.count(), filled=fill.count(),
                                    rejected=rejected.count(), fill_area_um2=round(fill.area() * dbu * dbu, 4))
    return report
