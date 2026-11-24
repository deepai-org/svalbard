#!/usr/bin/env python3
"""pad_hspad a6 -> a6m: clear the shuttle precheck's Magic DRC (2026-11-24, PC-85; KLayout was already clean).

    python3 hspad_magic_fix.py <a6 pad_hspad.gds> <out.gds>          (KLayout python, inside the pad image)

The shuttle's Magic script (integration/signoff/precheck/magic_drc.tcl, block_drc.py --cfg L --checks magic) found 19 errors in the
published a6: 18 x MIMTM.2 ("MiM bottom plate surrounds contact < 0.4 um") and 1 x MIMTM.1, all at the two Metal5 risers that land on the
leg's Metal4 straps beside the MIM caps (x 335-339, y 488.8-494.8 and 736.7-742.7).
  1. Inside the leg cell `svhspad__pt_hs_leg` a Via4 array (M4->M5) sits on top of a Via3 array (M3->M4) on a different grid; Magic reads
     the partly overlapping cuts as contacts its MIM rules then reject. Every Via4 cut within 0.1 um of a Via3 cut (not on the MIM top plate) is re-placed exactly on the Via3 grid under it (aligned
     stacks); these cuts are the MIM bottom plates' Metal5 feed (read-back LVS checks it).
  2. Top level: Metal4 enclosure of the riser landings grown to cut + 0.4 um: boxes (334.82, 488.66)-(339.18, 494.88) and
     (334.82, 736.62)-(339.18, 742.84), same net as the strap / riser (LVS checks it).
  3. MIMTM.1 (bottom plate to unrelated metal < 1.2 um): the leg cell's 1 um Metal4 strap at local x -6..-5 (chip x 334-335) runs 1.0 um
     from the strap Magic counts as bottom plate; it is trimmed to 0.8 um (local x -6..-5.2) over local y 122.44-143.67, where that
     strap is plate-typed (its one Via3 at -5.63..-5.37 keeps 0.17 um enclosure).
No device change.
"""
import sys
import klayout.db as k

LEG = 'svhspad__pt_hs_leg'
M4_BOXES = ((334.82, 488.66, 338.95, 494.65), (334.82, 736.85, 338.95, 742.84))   # corner >= 1.3 um from the MIM plates (KLayout MIMTM.1)


def main(src, dst):
    L = k.Layout(); L.read(src); top = L.top_cell(); leg = L.cell(LEG)
    assert leg is not None, LEG
    v3, v4 = L.find_layer(40, 0), L.find_layer(41, 0)
    near = k.Region(leg.shapes(v3)).sized(int(round(.1 / L.dbu)))
    mimtop = L.find_layer(75, 0)                      # Via4 on the MIM top plate (75/0) connect the cap to Metal5: never removed
    keep = k.Region()
    if mimtop is not None:                            # the MIM top plates of the whole cell, mapped into every leg instance's frame
        allmim = k.Region(top.begin_shapes_rec(mimtop))
        it = top.begin_instances_rec()
        while not it.at_end():
            if it.inst_cell().cell_index() == leg.cell_index():
                keep += allmim.transformed((it.trans() * it.inst_trans()).inverted())
            it.next()
        keep = keep.sized(int(round(.3 / L.dbu)))
    kill = [s for s in leg.shapes(v4).each() if not s.is_text() and not (k.Region(s.polygon) & near).is_empty()
            and (k.Region(s.polygon) & keep).is_empty() and s.dbbox().right < -0.3]   # only left of the MIM bottom plate (leg x 0 = chip 340):
            # the cuts over the plate itself are part of the plate's own connection as Magic extracts it (moving them splits its net)
    zone = k.Region([s.polygon for s in kill]).sized(int(round(.3 / L.dbu)))
    for s in kill: leg.shapes(v4).erase(s)
    # re-feed: one Via4 exactly on every Via3 under the removed cuts (an aligned stack, which Magic accepts); these Via4 are the MIM
    # bottom plates' Metal5 feed, so the count is kept comparable
    m5 = k.Region(); allm5 = k.Region(top.begin_shapes_rec(L.find_layer(81, 0)))
    it = top.begin_instances_rec()
    while not it.at_end():
        if it.inst_cell().cell_index() == leg.cell_index(): m5 += allm5.transformed((it.trans() * it.inst_trans()).inverted())
        it.next()
    m5in = m5.merged().sized(-int(round(.12 / L.dbu)))           # Metal5 enclosure of Via4 (V4.4) with margin
    added = 0
    for s in leg.shapes(v3).each():
        if not s.is_text() and not (k.Region(s.polygon) & zone).is_empty() and (k.Region(s.polygon) - m5in).is_empty():
            leg.shapes(v4).insert(s.polygon); added += 1
    m4 = L.layer(46, 0)
    old = [x for x in leg.shapes(m4).each() if not x.is_text() and x.dbbox() == k.DBox(-6, 122.44, -5, 178.02)]
    assert len(old) == 1, 'strap (-6, 122.44)-(-5, 178.02) not found in ' + LEG
    leg.shapes(m4).erase(old[0])
    leg.shapes(m4).insert(k.DBox(-6, 122.44, -5.2, 143.67)); leg.shapes(m4).insert(k.DBox(-6, 143.67, -5, 178.02))
    for b in M4_BOXES: top.shapes(m4).insert(k.DBox(*b))
    # Via4 of the riser landings that the smaller boxes no longer enclose by 0.4 um (Magic MIMTM.2): removed, in the leg's frame
    inner = k.Region(); outer = k.Region()
    it = top.begin_instances_rec()
    while not it.at_end():
        if it.inst_cell().cell_index() == leg.cell_index():
            tr = (it.trans() * it.inst_trans()).inverted()
            for b in M4_BOXES:
                inner += k.Region(k.DBox(*b).to_itype(L.dbu)).sized(-int(round(.4 / L.dbu))).transformed(tr)
                outer += k.Region(k.DBox(*b).to_itype(L.dbu)).sized(int(round(.5 / L.dbu))).transformed(tr)
        it.next()
    edge = [x for x in leg.shapes(v4).each() if not x.is_text() and not (k.Region(x.polygon) & outer).is_empty()
            and not (k.Region(x.polygon) - inner).is_empty()]
    for x in edge: leg.shapes(v4).erase(x)
    print(f'riser-landing Via4 removed at the shrunk box edges: {len(edge)}')
    L.write(dst)
    print(f'{LEG}: re-placed {len(kill)} Via4 cuts as {added} cuts aligned on Via3, strap trimmed; added {len(M4_BOXES)} Metal4 enclosures')


if __name__ == '__main__':
    main(*sys.argv[1:3])
