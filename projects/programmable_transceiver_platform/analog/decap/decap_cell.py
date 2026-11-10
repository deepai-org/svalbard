"""MOS decoupling filler tile `pt_decap_tile` (GF180MCU, 3.3 V devices) and an example array.

Run inside KLayout (image sha256:bd7a70...):  klayout -b -r decap_cell.py -rd out=<dir> [-rd nx=5 -rd ny=5]

Circuit (no MOS gate on a rail; cross-coupled tie as in the PDK fillcap):
  MPCAP  pfet_03v3  D=S=B=VDD  G=GB     5 fingers W=28.5 L=6   (the capacitor, in the N-well)
  MNT    nfet_03v3  D=GB S=VSS G=G B=VSS 16 fingers W=4  L=0.5 (holds GB low; its Ron is the cap's series R)
  MPT    pfet_03v3  D=G  S=VDD G=GB B=VDD 1 finger  W=1  L=0.5 (holds G high; drives only MNT's gate)
Layers: COMP, NWELL, POLY2, NPLUS, PPLUS, CONTACT, METAL1, VIA1 + METAL2 (one G strap). Metal3-5 free.
Tile 40 x 40 um: VSS rail (M1) along y 0..1.2, VDD rail along y 38.8..40, both full width, so tiles abut
left/right; rows stack mirrored about x (VDD/VDD and VSS/VSS shared), like standard-cell rows.
"""
import pya, json
from pathlib import Path

W, H = 40., 40.
L = dict(comp=(22, 0), nwell=(21, 0), poly=(30, 0), nplus=(32, 0), pplus=(31, 0), cont=(33, 0),
         m1=(34, 0), via1=(35, 0), m2=(36, 0), m1lbl=(34, 10), bnd=(0, 0))
ly = pya.Layout(); ly.dbu = .001
tile = ly.create_cell('pt_decap_tile')
def box(cell, k, x0, y0, x1, y1):
    cell.shapes(ly.layer(*L[k])).insert(pya.DBox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
def contacts_col(cell, xc, y0, y1, pitch=.5):
    n = int((y1 - y0 - .22) / pitch) + 1; off = (y1 - y0 - .22 - (n - 1) * pitch) / 2
    for i in range(n):
        y = y0 + off + i * pitch; box(cell, 'cont', xc - .11, y, xc + .11, y + .22)
def contacts_row(cell, yc, x0, x1, pitch=.5):
    n = int((x1 - x0 - .22) / pitch) + 1; off = (x1 - x0 - .22 - (n - 1) * pitch) / 2
    for i in range(n):
        x = x0 + off + i * pitch; box(cell, 'cont', x, yc - .11, x + .22, yc + .11)
def via(cell, x, y):
    box(cell, 'via1', x - .13, y - .13, x + .13, y + .13)
    box(cell, 'm1', x - .2, y - .2, x + .2, y + .2); box(cell, 'm2', x - .2, y - .2, x + .2, y + .2)

C = tile; SD = .6; MW = .36
# rails
box(C, 'm1', 0, 0, W, 1.2); box(C, 'm1', 0, H - 1.2, W, H)
# P-substrate tap under VSS, N-well tap under VDD
box(C, 'comp', .5, .4, W - .5, .8); box(C, 'pplus', .3, .2, W - .3, 1.0); contacts_row(C, .6, .5, W - .5)
box(C, 'nwell', 0, 8.0, W, H)
box(C, 'comp', .5, H - .8, W - .5, H - .4); box(C, 'nplus', .3, H - 1.0, W - .3, H - .2); contacts_row(C, H - .6, .5, W - .5)

# MPCAP: COMP y 10..37.5, 5 fingers L=6 starting x 1.0
cy0, cy1, nf, lg = 10., 37.5, 5, 6.
x = 1.
cols = []
for i in range(nf + 1):
    cols.append(x); x += SD
    if i < nf:
        box(C, 'poly', x, 8.8, x + lg, cy1 + .4); x += lg
cap_x1 = x
box(C, 'comp', 1., cy0, cap_x1, cy1); box(C, 'pplus', .7, cy0 - .3, cap_x1 + .3, cy1 + .3)
for cx in cols:
    xc = cx + SD / 2; contacts_col(C, xc, cy0 + .1, cy1 - .1)
    box(C, 'm1', xc - MW / 2, cy0 + .05, xc + MW / 2, H - 1.2)          # S/D/B -> VDD rail
# GB poly bar under the fingers, contacted; GB M1 bar
gb_y0, gb_y1 = 8.4, 9.2
box(C, 'poly', 1., gb_y0, 37.0, gb_y1); contacts_row(C, (gb_y0 + gb_y1) / 2, 1.2, 36.8)
box(C, 'm1', 1., gb_y0 + .05, 37.0, gb_y1 - .05)
cap_info = dict(x=[1., cap_x1], y=[cy0, cy1], fingers=nf, L=lg, W=cy1 - cy0)

# MPT: tiny PMOS tie at x 36..37.7 (after cap_x1=34.6), COMP y 10.5..11.5, gate poly rises from the GB bar
px0 = 35.8
box(C, 'comp', px0, 10.5, px0 + 1.7, 11.5); box(C, 'pplus', px0 - .3, 10.2, px0 + 2.0, 11.8)
# N-well tap near the PMOS devices (DF.13: PCOMP within 20 um of an N-well tap)
box(C, 'comp', 38.3, 9.6, 39.3, 37.6); box(C, 'nplus', 38.0, 9.3, 39.6, 37.9); contacts_col(C, 38.8, 9.7, 37.5)
box(C, 'm1', 38.62, 9.65, 38.98, H - 1.2)
box(C, 'poly', px0 + .6, gb_y1 - .1, px0 + 1.1, 11.9)
contacts_col(C, px0 + .3, 10.6, 11.4); contacts_col(C, px0 + 1.4, 10.6, 11.4)
box(C, 'm1', px0 + .3 - MW / 2, 10.55, px0 + .3 + MW / 2, H - 1.2)       # source -> VDD
box(C, 'm1', px0 + 1.4 - MW / 2, 10.55, px0 + 1.4 + MW / 2, 12.2)       # drain = G
via(C, px0 + 1.4, 12.0)

# MNT: 16 fingers L=0.5, COMP y 2.4..6.4, gate bar (G) below at y 1.5..2.0
ny0, ny1, nnf, nl = 2.4, 6.4, 16, .5
x = 1.; ncols = []
for i in range(nnf + 1):
    ncols.append(x); x += SD
    if i < nnf:
        box(C, 'poly', x, 1.5, x + nl, ny1 + .4); x += nl
mnt_x1 = x
box(C, 'comp', 1., ny0, mnt_x1, ny1); box(C, 'nplus', .7, ny0 - .3, mnt_x1 + .3, ny1 + .3)
box(C, 'poly', 1.6, 1.5, mnt_x1 + 1.4, 2.0)           # G bar (between first and last finger, extended right)
for i, cx in enumerate(ncols):
    xc = cx + SD / 2; contacts_col(C, xc, ny0 + .1, ny1 - .1)
    if i % 2 == 0:
        box(C, 'm1', xc - MW / 2, 0, xc + MW / 2, ny1 - .05)            # source -> VSS rail
    else:
        box(C, 'm1', xc - MW / 2, ny0 + .05, xc + MW / 2, gb_y0 + .4)   # drain -> GB bar
# G contact at the right end of the bar, strap to MPT drain on Metal2
gx = mnt_x1 + .9
box(C, 'poly', gx - .4, 1.4, gx + .4, 2.1); contacts_row(C, 1.75, gx - .3, gx + .3)
box(C, 'm1', gx - .4, 1.45, gx + .4, 2.05); via(C, gx, 1.75)
box(C, 'm2', gx - .2, 1.55, px0 + 1.6, 1.95); box(C, 'm2', px0 + 1.2, 1.55, px0 + 1.6, 12.2)
box(C, 'bnd', 0, 0, W, H)
for t, y in (('VSS', .6), ('VDD', H - .6)):
    C.shapes(ly.layer(*L['m1lbl'])).insert(pya.DText(t, pya.DTrans(W / 2, y)))

# example array: rows mirrored about x so rails are shared
nx = int(globals().get('nx', 5)); nyr = int(globals().get('ny', 5))
arr = ly.create_cell('pt_decap_array')
for j in range(nyr):
    for i in range(nx):
        t = pya.DTrans(i * W, j * H) if j % 2 == 0 else pya.DTrans(pya.DTrans.M0, i * W, (j + 1) * H)
        arr.insert(pya.DCellInstArray(tile.cell_index(), t))
for t, y in (('VSS', .6), ('VDD', H - .6)):
    arr.shapes(ly.layer(*L['m1lbl'])).insert(pya.DText(t, pya.DTrans(W / 2, y)))
o = Path(out); o.mkdir(parents=True, exist_ok=True)
for cell in (tile, arr):
    opt = pya.SaveLayoutOptions(); opt.select_cell(cell.cell_index()); ly.write(str(o / f'{cell.name}.gds'), opt)
gate_um2 = nf * lg * (cy1 - cy0)
(o / 'tile.json').write_text(json.dumps(dict(cell='pt_decap_tile', size_um=[W, H], cap=cap_info, cap_gate_um2=gate_um2,
    mnt=dict(fingers=nnf, W=ny1 - ny0, L=nl), mpt=dict(W=1., L=.5), array=dict(nx=nx, ny=nyr)), indent=1) + '\n')
print('OK', gate_um2)
