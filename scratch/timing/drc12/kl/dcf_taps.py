# KLayout batch script: clear DCF.1a ("no 20 x 20 um area without COMP") inside a block by adding small floating P+
# substrate taps (COMP 0.6 x 0.6 under PPLUS 1.0 x 1.0) in the bands the chip filler cannot reach (dense Poly2 routing).
#   klayout -b -zz -r dcf_taps.py -rd gds=<in.gds> -rd top=<cell> -rd out=<out.gds> [-rd report=<json>]
# The taps sit in p-substrate only (outside Nwell / DNWELL / LVPWELL / Dualgate by a margin), away from Poly2, COMP and
# implants; they form no device (LVS unchanged) and carry no metal. DCF.1a is evaluated standalone on the block extent,
# with the deck's own exclusions (NDMY, RES_MK, Pad, IND_MK, well rings), so open areas the chip filler would fill also
# get taps: the result is stricter than the chip-level check.
import pya, json

ly = pya.Layout(); ly.read(gds)
top_cell = ly.cell(top)
dbu = ly.dbu
um = lambda v: int(round(v / dbu))
L = lambda a, b: ly.layer(a, b)
R = lambda a, b: pya.Region(top_cell.begin_shapes_rec(L(a, b))).merged()

comp, cdum, poly, npl, ppl = R(22, 0), R(22, 4), R(30, 0), R(32, 0), R(31, 0)
nw, dnw, lvpw, dg = R(21, 0), R(12, 0), R(204, 0), R(55, 0)
ndmy, resmk, pad, ind = R(111, 5), R(110, 5), R(37, 0), R(151, 5)
ext = pya.Region(top_cell.bbox())

ring = lambda r, s: r.sized(um(s)) - r.sized(-um(s))
excl = ndmy + resmk + pad + ind + ring(nw, 1) + ring(dnw, 2) + ring(lvpw, 1) + ring(dg, 1)   # the deck's DCF.1a keep-out


def dcf1a(c):
    return (ext - c - excl).sized(-um(10)).sized(um(10))


# where a tap centre may go: PPLUS square half 0.5 um, plus margins (PP-poly 0.3, PP-COMP 1.0, PP-NP/PP 0.6, wells)
HALF = 0.5
block = (poly.sized(um(0.3)) + comp.sized(um(1.0)) + cdum.sized(um(1.0)) + npl.sized(um(0.6)) + ppl.sized(um(0.6))
         + nw.sized(um(1.5)) + dnw.sized(um(4.0)) + lvpw.sized(um(1.5)) + dg.sized(um(1.0))
         + (ndmy + resmk + pad + ind).sized(um(1.0)) + (ext - ext.sized(-um(1.0))))
allowed = (ext - block).sized(-um(HALF))

fail0 = dcf1a(comp + cdum)
taps = pya.Region()
PITCH = 6.0
for it in range(4):
    fail = dcf1a(comp + cdum + taps)
    if fail.is_empty():
        break
    cand = (allowed & fail.sized(um(2))) - taps.sized(um(1.0 + HALF))
    b = fail.bbox()
    added = 0
    y = b.bottom
    while y < b.top:
        x = b.left
        while x < b.right:
            cell = cand & pya.Region(pya.Box(x, y, x + um(PITCH), y + um(PITCH)))
            if not cell.is_empty():
                p = next(cell.each_merged())
                cv = p.decompose_convex()[0]
                pts = list(cv.each_point())
                cx = sum(q.x for q in pts) // len(pts); cy = sum(q.y for q in pts) // len(pts)
                cx, cy = um(round(cx * dbu / 0.005) * 0.005), um(round(cy * dbu / 0.005) * 0.005)
                if not cand.interacting(pya.Region(pya.Box(cx - 1, cy - 1, cx + 1, cy + 1))).is_empty():
                    t = pya.Box(cx - um(0.3), cy - um(0.3), cx + um(0.3), cy + um(0.3))
                    taps.insert(t)
                    cand -= pya.Region(t).sized(um(1.0 + 2 * HALF))
                    added += 1
            x += um(PITCH)
        y += um(PITCH)
    if not added:
        break

tc = ly.create_cell(top + '_dcf_taps')
for t in taps.each():
    t = t.bbox(); tc.shapes(L(22, 0)).insert(t)
    tc.shapes(L(31, 0)).insert(t.enlarged(um(0.2), um(0.2)))
top_cell.insert(pya.CellInstArray(tc.cell_index(), pya.Trans()))
ly.write(out)
left = dcf1a(comp + cdum + taps)
rep = dict(gds=gds, top=top, taps=taps.count(), dcf1a_before=fail0.count(), dcf1a_after=left.count(),
           left_boxes=[[round(v * dbu, 2) for v in (q.bbox().left, q.bbox().bottom, q.bbox().right, q.bbox().top)]
                       for q in left.each()])
print(json.dumps(rep))
if globals().get('report'):
    open(report, 'w').write(json.dumps(rep, indent=1))
