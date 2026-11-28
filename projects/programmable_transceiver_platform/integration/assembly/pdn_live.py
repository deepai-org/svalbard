"""Grid liveness: Metal4 / Metal5 pieces joined through Via4 to a seed (pad-fed ring stubs). Used by kl_place for dead slots
and dead_piece_pins. Via4 is every cut in the pdn cell: via-array instances (outlines) AND plain cut shapes (via_fill writes
both; 1fb2938c counted only the instances and flagged live pins dead on plan-rf11: isw_lod / isw_lo VDD, rx_ref_in /
pll_vreg2 VSS, all live by extraction). Selftest: python3 pdn_live.py (known-answer cases)."""
import klayout.db as db


def via4_region(ly, pdn, v4_layer, v4_cell):
    r = db.Region([i_.bbox() for i_ in pdn.each_inst() if v4_cell and i_.cell_index == v4_cell.cell_index()])
    r.insert(pdn.shapes(v4_layer))
    return r.merged()


def live(m4, m5, v4, seed):
    k4 = m4.interacting(seed); k5 = m5.interacting(v4.interacting(k4)) + m5.interacting(seed)
    while True:
        n5 = (m5.interacting(v4.interacting(k4)) + k5).merged(); n4 = (m4.interacting(v4.interacting(n5)) + k4).merged()
        if n4.count() == k4.count() and n5.count() == k5.count(): return k4, k5
        k4, k5 = n4, n5


def selftest():
    ly = db.Layout(); ly.dbu = 0.001; pdn = ly.create_cell('pdn'); v4 = ly.layer(41, 0)
    vc = ly.create_cell('via_x'); vc.shapes(v4).insert(db.Box(0, 0, 260, 260))
    B = lambda *a: db.Box(*[int(v*1000) for v in a])
    m4 = db.Region([B(0, 0, 10, 100), B(50, 0, 60, 100), B(100, 0, 110, 100), B(150, 0, 160, 100)])   # A seeded, B, C, D
    m5 = db.Region([B(0, 40, 70, 50), B(90, 70, 120, 80)])          # row joins A-B; row on C only
    pdn.insert(db.CellInstArray(vc.cell_index(), db.Trans(db.Vector(2000, 42000))))      # A-row: instance cut
    pdn.shapes(v4).insert(B(52, 42, 52.26, 42.26))                                        # B-row: plain cut (the 1fb2938c miss)
    seed = db.Region(B(0, 0, 10, 5))
    k4, _ = live(m4, m5, via4_region(ly, pdn, v4, vc), seed)
    got = [not (k4 & db.Region(B(x, 10, x+1, 11))).is_empty() for x in (0, 50, 100, 150)]
    exp = [True, True, False, False]
    k4i, _ = live(m4, m5, db.Region([i_.bbox() for i_ in pdn.each_inst()]).merged(), seed)      # negative control: instances only
    neg = not (k4i & db.Region(B(50, 10, 51, 11))).is_empty()
    ok = got == exp and neg is False
    print('pdn_live selftest', 'PASS' if ok else 'FAIL', got, 'instances-only B live:', neg)
    return 0 if ok else 1


if __name__ == '__main__':
    import sys; sys.exit(selftest())
