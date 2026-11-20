# pt_pll_ring r12 ECO (TIM-17 option 2): ct_phbuf8 -> ct_phbuf8m (same pins + M0..M7 ports), ct_xc4 (duty pairs) in the
# free band above, M2 out of the M pins to Metal3 risers in a 10 um strip added on the east side, supplies by M1/M3.
import pya
ly = pya.Layout(); ly.read(gds); top = ly.cell('pt_pll_ring'); dbu = ly.dbu
F = '/repo/projects/programmable_transceiver_platform/analog/timing/generated/fast/'
def imp(name):
    src = pya.Layout(); src.read(F + name + '.gds'); mp = {}
    def copy(sc, pre):
        dc = ly.create_cell(pre + sc.name)
        for li in src.layer_indexes(): dc.shapes(ly.layer(src.get_info(li))).insert(sc.shapes(li))
        for inst in sc.each_inst():
            if inst.cell.cell_index() not in mp: mp[inst.cell.cell_index()] = copy(inst.cell, pre)
            ia = inst.cell_inst.dup(); ia.cell_index = mp[inst.cell.cell_index()].cell_index(); dc.insert(ia)
        return dc
    return copy(src.cell(name), 'pll_ring__')
pb = imp('ct_phbuf8m'); xc = imp('ct_xc4')
for inst in list(top.each_inst()):
    if inst.cell.name.endswith('__ct_phbuf8'):
        tr = inst.trans; inst.delete(); top.insert(pya.CellInstArray(pb.cell_index(), tr))
PX, PY = 98.15, 496.42; OX, OY = 175.7, 576.0
top.insert(pya.CellInstArray(xc.cell_index(), pya.Trans(pya.Point(int(round(OX / dbu)), int(round(OY / dbu))))))
L = {n: ly.layer(*v) for n, v in dict(m1=(34, 0), v1=(35, 0), m2=(36, 0), v2=(38, 0), m3=(42, 0)).items()}
def box(l, x1, y1, x2, y2): top.shapes(L[l]).insert(pya.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
def via2(x, y): box('m2', x - .2, y - .2, x + .2, y + .2); box('v2', x - .13, y - .13, x + .13, y + .13); box('m3', x - .2, y - .2, x + .2, y + .2)
def via1(x, y): box('m1', x - .19, y - .19, x + .19, y + .19); box('v1', x - .13, y - .13, x + .13, y + .13); box('m2', x - .2, y - .2, x + .2, y + .2)
for k in range(8):
    xl, yl = PX + 84.27 + 0.9 * k, PY + 10.9 + 0.75 * k            # phbuf8m pin
    xu, yu = OX + 14.42 + 0.9 * k, OY + 3.9 + 0.75 * k             # xc4 pin
    xr = 199.3 + 0.9 * k
    box('m2', xl - .2, yl - .2, xr + .2, yl + .2); via2(xr, yl)
    box('m3', xr - .2, yl, xr + .2, yu); via2(xr, yu); box('m2', xu - .2, yu - .2, xr + .2, yu + .2)
# supplies: phbuf rails (M1, VSS bottom y 0.3, VDD top) -> xc4 rails
pw = 91.77; ph = 37.2; xw = 21.92; xh = 15.45
yvs0, yvd0 = PY + 0.3, PY + ph - 0.3; yvs1, yvd1 = OY + 0.3, OY + xh - 0.3
XD, XS = 207.0, 208.6
box("m1", PX + 60, yvd0 - .25, XD + .25, yvd0 + .25); box('m1', XD - .25, yvd0, XD + .25, yvd1); box("m1", OX + 8, yvd1 - .25, XD + .25, yvd1 + .25)
box("m1", PX + 60, yvs0 - .25, XS + .25, yvs0 + .25); via1(XS, yvs0); via2(XS, yvs0)
box('m3', XS - .2, yvs0, XS + .2, yvs1); via2(XS, yvs1); box('m2', OX + 8, yvs1 - .2, XS + .2, yvs1 + .2); via1(OX + 8, yvs1); box('m1', OX + 8, yvs1 - .25, OX + 12, yvs1 + .25)
ly.cleanup(); ly.write(out); print('ok', top.dbbox())
