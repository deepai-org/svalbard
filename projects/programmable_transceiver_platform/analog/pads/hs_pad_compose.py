#!/usr/bin/env python3
"""PD21 low-C SATA/PCIe RX pad pair `pad_hspad` = protection shell + two pt_hs_leg blocks.

  shell : protection_pad_ss pair on network-gc-d2 (x2 up-diodes), escape 8 um, 12 um trunks, 4 um boundary pins
          (PAD_P x 286-290, PAD_N x 302-306 at y 912.91)
  legs  : pt_hs_leg (hs_leg_layout.py); P mirrored (M90) at x 285, N at x 326, bottom y 925
  straps: PAD_P straight up (M5 x 288) / PAD_N jog (M5 y 917 to x 323) into the legs' PAD trunks (M4, via4);
          shared leg nets joined by M5 straps above the legs; RAILPRE (precharge diode) down the N bank (M4 x 313.8)
          to the shell ATB_ESD_RAIL tap (M3 y 436.5 -> x 91.58); leg VSS down (M4 x 316) to the pad return
          (M3 y 428 -> M5 return vertical at x 138).
    python3 hs_pad_compose.py <work> <shell dir> <leg dir> <network dir> [--stacked]

  --stacked (area pass 4, 2026-11-13; RX pins co-located for review condition 2): same shell, same leg master, legs
          stacked BESIDE the shell instead of above it, so the cell keeps the 912.91 um shell depth (bbox 492 x 912.91
          instead of 478 x 1111.25, -0.088 mm2 of core). P leg (unmirrored) at x 340, y 440; N leg MIRRORED in y (M0) above
          it, so both legs' trunk ends (leg "top") face one 42 um channel between them and everything in the channel
          is mirror-symmetric about its midline.
          PAD_P: M5 at y 414-418 from the shell PAD_P trunk (M5 x 282-294, starts y 410) under the start of the PAD_N
          trunk (y 426: no P/N crossing), then up the P leg PAD trunk; PAD_N: M5 strap from the shell PAD_N trunk
          (x 298-310) to the N leg PAD trunk, plus an unconnected-end M5 balance stub that mirrors the PAD_P run over
          the bank (pad P/N C balance).
          Shared nets: the M4 trunks of the two legs are joined straight across the channel; every port net also gets
          a 1 um M5 strap to the side edge (x 492), 5 levels below and 4 above the RX pair.
          RX_P / RX_N: mirror-identical routes (M4 trunk extension 18 um, 0.6 um M5 strap) to ADJACENT side pins at
          x 492, 6 um apart, in the middle of the channel. RAILPRE / VSS down from the P-leg bank exactly as before.

  R-fixed leg (PC-14, 2026-11-14): when the leg's layout-info.json carries `r_fix` (hs_leg_layout.py default build), the
          stacked composer also
          - joins the two legs' TERM_VCM straps (30 um Metal4+Metal5 at the leg tops) with a 23 um Metal4 trunk across the
            channel and taps the TERM_VCM pin strap from the channel MIDLINE (Metal4 bridge + finger + via4 array), the old
            single via4 on the 1 um trunk is dropped;
          - leaves the PAD feed's via4 array to the leg (landing pad there) instead of its own 3 x 3 stack;
          - adds via4 arrays where the shell joins its Metal4 PAD trunks to the Metal5 trunks with ONE cut each
            ((288, 416) for PAD_P, (304, 432) for PAD_N): the whole termination current runs through those cuts;
          - keeps the channel and every pin where they were when the leg height changes (P leg anchored at its top).
          A legacy leg (no `r_fix`) gives the published geometry.

  ESD / pad-side overlays (PC-15, 2026-11-18, `esd_overlays`, R-fixed build only): same-net metal and via arrays in the top cell on
          the shell's bond pad -> diode, diode -> clamp and VSS return paths (shell, network and array generators are not edited).
          Ring band (y < 396): only the two VSS Metal2 strips are widened; no Metal3-5, no Via3 / Via4 there.

  --site-primary[=JSON] (PC-27, 2026-11-18, option A of the ESD metal review; R-fixed stacked build only; default OFF = published
          geometry): primary diodes inside both pad sites (x0 = 0 and 211), tied straight to the ring rails, drawn by
          pad_site_primary.py (5 x nd2ps to ring DVSS + 5 x pd2nw to ring DVDD per pad by default; JSON = overrides of its OPT).
          New port `DVDD` (Metal3 landings under the ring DVDD bands; reaches the ring only under the rail cell).  The
          shell's isolated-rail network stays as the secondary stage behind the Metal2 neck.
  --no-core-array (only with --site-primary): the shell's diode array (4 nd2ps + 8 pd2nw per pad on the isolated rail) is deleted
          from the composed cell and the overlays that served it are not drawn; the isolated rail, its clamps and the array's
          feed bars stay in the shell as they are (no pad diode left on the rail).
  --sec (PC-36 candidate a5, 2026-11-19; only with --site-primary and a leg built with hs_leg_layout.py --sec; default OFF):
          LOCAL SECONDARY CLAMP. The leg carries one pd2nw per termination unit (switch drain -> DVDD) and a DVDD trunk (outermost
          in the bank). The composer joins the two legs' DVDD trunks across the channel and routes DVDD from the P leg's trunk
          down the left of the P leg (Metal4, y 398-404 west to the N site column), down the N site column (Metal4 to y 352,
          Via3 / Via2 arrays above the rail cell, Metal2 x 258-282 down to the site DVDD bar at y 148.7). The taller leg reaches
          below y 431: the VSS strap (y 428) then runs below the leg (y 406.5) to the shell's Metal5 VSS return at x 138.
          DVDD is reinforced beside the legs (Metal4 x 311.5 .. trunk up to the N leg's DVDD track, Metal5 y 419-735.5, Via3 / Via4 arrays).
          A leg without DVDD and no --sec = the geometry above, unchanged.
  --esd-opt=JSON: overrides of ESD_OPT (R-fixed build), e.g. '{"neck_m1": true, "p_trunk_m5_to": 282}'; default = published geometry.
"""
import json, re, shutil, subprocess, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
LEGX_P, LEGX_N, LEGY = 285., 326., 925.
SHARED = ['VSS', 'VDD', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VBIAS', 'RAILPRE']
PORTS = ['PAD_P', 'PAD_N', 'RX_P', 'RX_N', 'VBIAS', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VDD', 'VSS']


def assemble(work):
    import klayout.db as k
    cfg = json.loads((work / 'config.json').read_text())
    if cfg.get('stacked'):
        return assemble_stacked(work, cfg)
    tx = cfg['trunk_x']; ltop = cfg['leg_top']
    l = k.Layout(); l.read(str(work / 'shell.gds'))
    shell = l.cell('rf_protected_pad_pair')
    l.read(str(work / 'leg.gds')); leg = l.cell('pt_hs_leg')
    for c in l.each_cell():
        for ix in l.layer_indexes():
            for s in list(c.each_shape(ix)):
                if s.is_text(): s.delete()
    root = l.create_cell('pad_hspad')
    root.insert(k.DCellInstArray(shell.cell_index(), k.DTrans(0., 0.)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(k.DTrans.M90, LEGX_P, LEGY)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(LEGX_N, LEGY)))
    M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}
    def box(layer, x1, y1, x2, y2): root.shapes(l.layer(layer, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    def wire(m, a, b, w):
        h = w / 2; box(M[m], min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)
    def stack(x, y, lo, hi, n=1):
        h = .4 + .3 * (n - 1)          # M5 pad >= 0.64 um2 (MT.4)
        for m in range(lo, hi + 1): box(M[m], x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            for i in range(n):
                for j in range(n):
                    cx = x + (i - (n - 1) / 2) * .6; cy = y + (j - (n - 1) / 2) * .6
                    box(V[m], cx - .13, cy - .13, cx + .13, cy + .13)
    px = lambda net: LEGX_P - tx[net]      # mirrored P leg
    nx = lambda net: LEGX_N + tx[net]
    yp = LEGY + cfg['pad_trunk_lo'] + 1.5  # inside the PAD trunk span, below the MIM row
    # PAD_P: shell pin (286-290) straight up on M5 to the P leg PAD trunk (x 288)
    wire(5, (288., 912.), (288., yp), 4.); stack(288., yp, 4, 5, 3)
    # PAD_N: shell pin (302-306) up to 917, jog right to x 323 (N leg PAD trunk), up into the trunk
    wire(5, (304., 912.), (304., 917.), 4.); wire(5, (302., 917.), (nx('PAD') + 2., 917.), 4.)
    wire(5, (nx('PAD'), 917.), (nx('PAD'), yp), 4.); stack(nx('PAD'), yp, 4, 5, 3)
    # shared nets: M4 trunk extensions above the legs + one M5 strap per net
    top = LEGY + ltop
    for i, net in enumerate(SHARED):
        y = top + 4. + 2.5 * i; w = 2. if net == 'VSS' else .5
        for x in (px(net), nx(net)):
            wire(4, (x, top - 1.), (x, y), w); stack(x, y, 4, 5)
        wire(5, (px(net), y), (nx(net), y), 1.)
    ymax = top + 4. + 2.5 * len(SHARED) + 2.
    for net, x in (('RX_P', px('RX')), ('RX_N', nx('RX'))):
        wire(4, (x, top - 1.), (x, ymax), 1.); stack(x, ymax - .5, 4, 5)
    # RAILPRE: N bank trunk (M4) down to y 436.5, M3 left to the ATB tap stub (91.58, 438.2)
    xr = nx('RAILPRE'); ylo = LEGY + cfg['railpre_lo'] + 1.
    wire(4, (xr, ylo), (xr, 436.5), .5); stack(xr, 436.5, 3, 4)
    wire(3, (xr, 436.5), (91.58, 436.5), .5); wire(3, (91.58, 436.25), (91.58, 438.4), .5)
    # VSS: N bank VSS trunk (M4, 2 um) down to y 428, M3 left to x 138, up to the pad return M5 (x 136-140, y 400-444)
    xv = nx('VSS'); yv = LEGY + cfg['vss_lo'] + 1.
    wire(4, (xv, yv), (xv, 428.), 2.); stack(xv, 428., 3, 4, 2)
    wire(3, (xv, 428.), (138., 428.), 1.); stack(138., 428., 3, 5, 2)
    T = lambda name, m, x, y: root.shapes(l.layer(M[m], 10)).insert(k.DText(name, k.DTrans(x, y)))
    for i, net in enumerate(SHARED):
        if net != 'RAILPRE': T(net, 5, (px(net) + nx(net)) / 2, top + 4. + 2.5 * i)
    T('RX_P', 5, px('RX'), ymax - .5); T('RX_N', 5, nx('RX'), ymax - .5)
    T('PAD_P', 5, 288., 905.); T('PAD_N', 5, 304., 905.)
    T('ESD_RAIL', 3, 130., 444.)   # internal rail named for the model wrapper / well audit (RAILPRE stays unlabelled: observed as an internal node)
    import marker_merge
    (work / 'marker-merge.json').write_text(json.dumps(marker_merge.merge(l, root), indent=1) + '\n')
    for c in l.each_cell():
        if c.cell_index() != root.cell_index() and not c.name.startswith('svhspad__'):
            c.name = 'svhspad__' + c.name
    o = k.SaveLayoutOptions(); o.add_cell(root.cell_index()); l.write(str(work / 'pad_hspad.gds'), o)
    b = root.dbbox(); (work / 'geometry.json').write_text(json.dumps(dict(bbox_um=[b.left, b.bottom, b.right, b.top], area_um2=b.width() * b.height())) + '\n')


# PC-15 overlay options (stacked, R-fixed build only).  All coordinates are pad_hspad um; the shell places the protection
# network at (0, 440) and its diode array at (150, 460) (fingers at x 150 + 8 i; rows nd2ps/pd2nw per leg, see protection_array.py).
ESD_OPT = dict(
    p_trunk_m5_to=183.,       # PAD_P Metal5 overlay on the Metal4 trunk ends here (at least the feeder; 279 = almost up to the Metal5 trunk)
    n_riser_to=310.,          # PAD_N Metal5 riser (x 302-306, y 506-738) widened to this x (306 = unchanged); keeps bond -> heads P / N equal
    neck_m1=False,            # PC-27: Metal1 under both Metal2 escape necks (8 um, y 67-408 / 424), tied with Via1 arrays: halves the neck's
                              # 4.0 ohm in the signal path.  Interrupted at the rail cell's Metal1 frame (y 65.5-66.2, 349.2-349.8) and at the
                              # pad-site VSS bridge (y 96.3-99.0).  Set by --esd-opt='{"neck_m1": true}'.
)


def esd_overlays(box, M, V, varray, opt=ESD_OPT, core_array=True):
    """Same-net metal / via overlays on the shell's pad-side and ESD paths (shell, network and array cells are not edited).
    PAD_P / PAD_N: via arrays where the Metal2 neck meets the Metal4 trunk, Metal5 over the trunks, a Metal5 feeder per pad
    right of the diode array, a Metal3 bar per diode row and a Metal1..Metal3 via column on every diode centre stripe.
    VSS: Metal1 widening + via columns on the nd2ps anode rings, Metal4 bars into the Metal4 VSS strip, via arrays at the
    single cuts of the return, Metal5 over the Metal4 VSS trunk, wider Metal2 strips to the ring VSS stacks.
    ESD_RAIL: Metal1 widening + via columns on the pd2nw cathode rings, Metal5 bars into a widened Metal5 rail strip,
    Metal5 / Metal4 / Metal3 link from that strip to the shunt clamp's rail plate.
    core_array=False (--no-core-array: the shell's diode array is deleted): only the signal-path overlays (neck -> trunk via
    arrays, Metal5 over the PAD trunks, PAD_N riser) and the VSS return overlays are drawn; nothing on the array rows, the
    array feeders / bars or the isolated rail."""
    def pad(lo, hi, x1, y1, x2, y2, pitch=.62, cuts=None):      # metal lo..hi over the box, via columns / arrays between
        for m in range(lo, hi + 1): box(M[m], x1, y1, x2, y2)
        for v in range(lo, hi):
            for b in (cuts or [(x1, y1, x2, y2)]): varray(v, *b, pitch=pitch)
    FX = [150. + 8. * i for i in range(4)]
    XP, XN = (178., 183.), (199., 204.)                        # Metal5 feeders, 16 um apart (the Metal3 pad buses are x 185-187 / 189-191)
    # --- PAD: diode rows (y0 of the row, centre yc of the via column / bar); row 460: a foreign Metal2 bar at y 458.5-459.0.
    # Per finger a Metal1-Metal3 via column on the centre stripe (the array's own Via1 is at y0), per row a 4.4 um Metal3 bar.
    # PAD_P: bar straight into the feeder.  PAD_N: the PAD_P Metal3 bus (x 185-187, all rows) is in the way -> Metal4 hop over it.
    if core_array:
        for pad_, rows in (('P', ((460., 463.1), (500., 500.), (620., 620.))), ('N', ((540., 540.), (580., 580.), (660., 660.)))):
            for y0, yc in rows:
                y1, y2 = yc - 2.2, yc + 2.2
                for fx in FX: pad(1, 3, fx - .385, y1, fx + .385, y2, pitch=.62)     # 7 cuts; in the rows with yc = y0 the middle Via1 is the array's own
                yb = min(y1, y0 - .5)                               # the Metal3 bar also covers the array's 0.48 um Metal2 bar at y0 ...
                for fx in FX:                                       # ... and ties it with a row of Via2 (else its single Via2 at the bus carries > 3 %)
                    varray(2, fx + .6, y0 - .33, min(fx + 7.4, 185.3 if pad_ == 'P' else 176.3), y0 + .33)
                if pad_ == 'P':
                    box(M[3], FX[0] - .385, yb, 187., y2); pad(3, 5, XP[0], y1, XP[1], y2, pitch=.7)   # Metal4 stops before the PAD_N Metal4 (x 184, y 494-506)
                else:
                    box(M[3], FX[0] - .385, yb, 176.5, y2); box(M[4], 166.5, y1, XN[1], y2)
                    varray(3, 166.9, y1, 173.1, y2); varray(3, 174.9, y1, 176.5, y2); varray(4, XN[0], y1, XN[1], y2)
                    varray(3, 189.3, y1, 190.7, y2)             # the hop also ties the PAD_N Metal3 bus (old path: one Via2 per row)
        box(M[5], XP[0], 411., XP[1], 623.)                         # PAD_P feeder, from the Metal4 trunk (y 410-422)
        box(M[5], XN[0], 495., XN[1], 663.)                         # PAD_N feeder, from the shell's Metal4 bar (x 184-310, y 494-506) ...
        varray(4, XN[0], 495., XN[1], 505.)
        box(M[5], XN[1], 496., 283., 504.); varray(4, XN[1], 496., 283., 504.)     # ... which gets Metal5 on top (inset 2 um; 3 um clear of the PAD_P Metal5 trunk x 286-290)
        varray(4, 298., 494., 310., 506., skip=(304., 500.))        # ... and an array around its single Via4 to the Metal5 trunk
        varray(4, 282., 474., 294., 486., skip=(288., 480.))        # same for the PAD_P bar (x 180-294, y 474-486): the old path stays in parallel
        for x, ya in ((186., 474.), (190., 494.)):                  # ... and Via3 columns beside the single Via3 bus -> bar cuts
            varray(3, x - .7, ya, x + .7, ya + 5.4); varray(3, x - .7, ya + 6.6, x + .7, ya + 12.)
    box(M[5], 243., 428., 279., 436.); varray(4, 243., 428., 279., 436.)        # Metal5 over the PAD_N Metal4 trunk (y 426-438), inset 2 um, 3 um clear of the PAD_P Metal5 trunk (x 282)
    # Metal5 over the PAD_P Metal4 trunk (inset 2 um), open at the VSS Metal5 strip (x 136-140)
    for x1, x2 in ((32., 135.4), (140.6, max(opt['p_trunk_m5_to'], XP[1]))):   # (ends at the feeder position also when there is no feeder)
        box(M[5], x1, 412., x2, 420.); varray(4, x1, 412., x2, 420.)
    # necks -> trunks: Metal3 pad + Via2 / Via3 arrays beside the shell's 3 x 3 stacks at (37.5, 416) / (248.5, 432)
    pad(2, 4, 33.7, 410.2, 41.3, 419.8, pitch=.7, cuts=[(33.7, 410.2, 36.3, 419.8), (38.7, 410.2, 41.3, 419.8)])
    pad(2, 4, 244.7, 429.2, 252.3, 435.8, pitch=.7, cuts=[(244.7, 429.2, 247.3, 435.8), (249.7, 429.2, 252.3, 435.8)])   # above the VSS Metal3 wire (y 427.3-428.7)
    if opt['n_riser_to'] > 306.: box(M[5], 302., 506., opt['n_riser_to'], 738.)
    if opt.get('neck_m1'):
        for x1, x2, ytop in ((33.5, 41.5, 408.), (244.5, 252.5, 424.)):
            for y1, y2 in ((67.2, 95.2), (100.1, 348.1), (350.9, ytop)):
                box(M[1], x1, y1, x2, y2); varray(1, x1, y1, x2, y2)
    if core_array:
        # --- VSS: nd2ps anode rings (rows 460, 540): ring Metal1 is 0.23 um wide -> widen outwards, via columns, Metal4 bar to the strip (x 132-141)
        for y0 in (460., 540.):
            yv = y0 - 8.
            for fx in FX:
                for s in (-1., 1.):
                    box(M[1], fx + s * .915, y0 - 13.195, fx + s * 1.7, y0 + 13.195)
                    pad(2, 4, fx + s * .95, yv - 2.5, fx + s * 1.7, yv + 2.5)
                    for b in ((yv - 2.5, yv - .45), (yv + .45, yv + 2.5)) if s > 0 else ((yv - 2.5, yv + 2.5),):     # the array's Via1 is at (fx + 1.03, yv)
                        varray(1, fx + s * .95, b[0], fx + s * 1.7, b[1], pitch=.62)
            box(M[4], 141., yv - 2.5, FX[3] + 1.7, yv + 2.5)
        # --- ESD_RAIL: pd2nw cathode rings (rows 500, 580, 620, 660), inside the SUB ring (Metal1 from fx +- 1.755; its via pad at y0 - 8, right side)
        for y0 in (500., 580., 620., 660.):
            yr = y0 + 8.
            for fx in FX:
                box(M[1], fx - 1.52, y0 - 13.155, fx - .875, y0 + 13.155)
                box(M[1], fx + .875, y0 - 13.155, fx + 1.52, y0 - 8.6); box(M[1], fx + .875, y0 - 7.4, fx + 1.52, y0 + 13.155)
                for s in (-1., 1.):
                    pad(2, 5, fx + s * .88, yr - 1.5, fx + s * 1.52, yr + 2.5)
                    for b in ((yr - 1.5, yr - .45), (yr + .45, yr + 2.5)) if s > 0 else ((yr - 1.5, yr + 2.5),):     # the array's Via1 is at (fx + 0.99, yr)
                        varray(1, fx + s * .88, b[0], fx + s * 1.52, b[1], pitch=.62)
            box(M[5], 134., yr - 1.5, FX[3] + 1.52, yr + 2.5)
        box(M[5], 134., 447., 146., 719.)                          # rail strip x 126-134 widened (over the Metal4 VSS strip, clear of the pad bars)
        box(M[5], 134., 713.5, 200., 741.5)                         # ... and on to the shunt clamp's rail plate (Metal2 / Metal3, y 745.2-768.7); 28 um: MSLOT5.1 (no Metal5 wider than 30 um)
        pad(4, 5, 146., 722., 200., 741.5, pitch=.7)
        box(M[3], 146., 722., 200., 745.3); varray(3, 146., 722., 200., 741.5)
        # canonical clamp (x 0-75): its rail Metal3 pads (y 712.2-718.8) reach the Metal5 rail bar through ONE Via3 / Via4 at (6.055, 715),
        # its VSS Metal3 columns (y 704.2-710.8) reach the Metal4 VSS through ONE Via3 at (12.905, 707)
        for x1, x2 in ((1.525, 10.585), (13.99, 23.67), (25.84, 35.52), (39.37, 49.05), (51.22, 60.9), (64.305, 73.365)):
            a, b = max(round(x1 + .115, 2), 2.3), round(x2 - .115, 2)       # the Metal5 rail bar starts at x 2.055
            box(M[4], a, 713.4, b, 718.7)
            for v in (3, 4):
                for c, d in ((a, 5.4), (6.7, b)) if x1 < 6. else ((a, b),): varray(v, c, 713.4, d, 718.7)
        for x1, x2 in ((12.405, 13.405), (24.255, 25.255), (36.325, 38.565), (49.635, 50.635), (61.485, 62.485)):
            for y1, y2 in ((704.21, 706.41), (707.59, 710.79)) if x1 < 13. else ((704.21, 710.79),): varray(3, x1, y1, x2, y2)
        # Metal3 under the Metal4 VSS strip (x 132-141) from the array to the wide Metal4 below the shunt clamp
        box(M[3], 132., 447., 141., 677.); varray(3, 132., 447., 141., 677.)
    # --- VSS return: arrays at the single cuts, Metal5 over the Metal4 trunk (y 396-404), wider Metal2 strips to the ring stacks
    varray(4, 136.2, 438.2, 139.8, 443.3); varray(4, 136.2, 400.6, 139.8, 403.8)
    box(M[5], 7., 396.5, 224., 401.5); varray(4, 7., 396.5, 135.5, 401.5); varray(4, 140.5, 396.5, 224., 401.5)
    for x1, x2, xs in ((.5, 25.5, 10.), (211.5, 236.5, 221.)):
        box(M[2], x1, 74.305, x2, 404.)
        a, b = max(x1, 6.) + .2, min(x2, 225.) - .2
        pad(3, 3, a, 396.2, b, 403.8)
        for v in (2, 3):
            varray(v, a, 396.2, xs - .7, 403.8); varray(v, xs + .7, 396.2, b, 403.8)


def assemble_stacked(work, cfg):
    import klayout.db as k
    tx = cfg['trunk_x']; ltop = cfg['leg_top']; lright = cfg['leg_right']   # leg bbox top / right edge (leg-local)
    fix = cfg.get('r_fix')
    X, Y_PLEG = 340., 594.75 - ltop    # P leg origin (unmirrored), anchored at its top (440 for the 154.75 um PD21 leg); side edge X + lright = 492
    EDGE, PITCH, RXSEP = 4., 2.5, 6.   # channel: leg edge / RX pair clearance, shared-strap pitch, RX_P-RX_N pin pitch
    LOW = ['TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VSS']   # straps between the P leg and RX_P
    HIGH = ['VDD', 'TERM_ENABLE', 'TERM_VCM', 'VBIAS', 'RAILPRE']           # straps between RX_N and the N leg
    if sorted(LOW + HIGH) != sorted(SHARED): raise ValueError('channel plan does not cover the shared nets')
    p_top = Y_PLEG + ltop                                   # P leg trunk ends
    level = {net: p_top + EDGE + PITCH * i for i, net in enumerate(LOW)}
    y_rxp = p_top + EDGE + PITCH * (len(LOW) - 1) + EDGE
    y_rxn = y_rxp + RXSEP
    level.update({net: y_rxn + EDGE + PITCH * i for i, net in enumerate(HIGH)})
    n_top = y_rxn + EDGE + PITCH * (len(HIGH) - 1) + EDGE   # N leg trunk ends (the mirrored leg's local top edge)
    Y_NLEG = n_top + ltop                                   # N leg origin; mirrored in y: global y = Y_NLEG - local y
    if abs((p_top + n_top) - (y_rxp + y_rxn)) > 1e-6: raise ValueError('channel is not symmetric about the RX pair')
    l = k.Layout(); l.read(str(work / 'shell.gds'))
    shell = l.cell('rf_protected_pad_pair')
    l.read(str(work / 'leg.gds')); leg = l.cell('pt_hs_leg')
    for c in l.each_cell():
        for ix in l.layer_indexes():
            for s in list(c.each_shape(ix)):
                if s.is_text(): s.delete()
    if not cfg.get('core_array', True):      # --no-core-array: delete the shell network's diode array (4 nd2ps + 8 pd2nw per pad)
        arr = [c for c in l.each_cell() if c.name.endswith('steering_array')]
        if len(arr) != 1: raise ValueError('expected exactly one steering_array cell in the shell')
        n_del = 0
        for c in l.each_cell():
            for inst in list(c.each_inst()):
                if inst.cell_index == arr[0].cell_index(): inst.delete(); n_del += 1
        if n_del != 1: raise ValueError(f'expected one steering_array instance, deleted {n_del}')
    if cfg.get('site_primary') is not None:
        # The shell ties VSS to the ring with a 2 x 2 um Metal2..Metal5 stack per site at (10, 78.3) / (221, 78.3).  Its Via3 / Via4 cuts do not
        # sit on the rail cell's via grid: on the provider rail cell they merge with its cuts (V3.1 / V3.2a / V4.1 / V4.2a in the pad-on-rail
        # precheck).  With the pad-site primaries VSS reaches ring Metal3 through their Via2 landings, so the stack keeps only Metal2 / Via2 / Metal3.
        n_rm = 0
        for x1 in (8.9, 219.9):
            w = k.DBox(x1, 77.2, x1 + 2.2, 79.4)
            for ln in (40, 41, 46, 81):
                li = l.find_layer(ln, 0)
                for sh in list(shell.shapes(li).each_overlapping(k.Box(*[round(v / l.dbu) for v in (w.left, w.bottom, w.right, w.top)]))):
                    if w.contains(sh.dbbox().p1) and w.contains(sh.dbbox().p2): sh.delete(); n_rm += 1
        if n_rm != 2 * (9 + 9 + 10 + 10): raise ValueError(f'ring stack: expected 76 shapes (2 x (9 Via3 + 9 Via4 + 10 Metal4 + 10 Metal5)), removed {n_rm}')
    root = l.create_cell('pad_hspad')
    root.insert(k.DCellInstArray(shell.cell_index(), k.DTrans(0., 0.)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(X, Y_PLEG)))                  # lower leg = P
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(k.DTrans.M0, X, Y_NLEG)))     # upper leg = N (mirrored in y)
    M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}
    def box(layer, x1, y1, x2, y2): root.shapes(l.layer(layer, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    def wire(m, a, b, w):
        h = w / 2; box(M[m], min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)
    def stack(x, y, lo, hi, n=1):
        h = .4 + .3 * (n - 1)
        for m in range(lo, hi + 1): box(M[m], x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            for i in range(n):
                for j in range(n):
                    cx = x + (i - (n - 1) / 2) * .6; cy = y + (j - (n - 1) / 2) * .6
                    box(V[m], cx - .13, cy - .13, cx + .13, cy + .13)
    T = lambda name, m, x, y: root.shapes(l.layer(M[m], 10)).insert(k.DText(name, k.DTrans(x, y)))
    tr = lambda net: X + tx[net]
    xpad = tr('PAD'); xedge = X + lright
    # P leg: shell PAD_P M5 trunk (x 282-294, from y 410) -> M5 at y 416, BELOW the PAD_N trunk start (y 426), so the
    # pair never crosses -> up over the P leg bank to the via stack on the P leg PAD trunk
    y_padp = Y_PLEG + cfg['pad_trunk_lo'] + 1.5
    box(M[5], 282., 414., xpad + 2., 418.); box(M[5], xpad - 2., 414., xpad + 2., y_padp)
    if not fix: stack(xpad, y_padp, 4, 5, 3)      # R-fixed leg: the leg has its own landing pad + via4 array there
    # N leg: shell PAD_N M5 trunk (x 298-310) sideways into the N leg PAD trunk; the stub beyond the via stack mirrors
    # the PAD_P run over the bank (same length, same leg metal underneath) and ends open: P/N pad C balance only
    y_padn = Y_NLEG - (cfg['pad_trunk_lo'] + 1.5)
    box(M[5], 298., y_padn - 2., xpad + 2., y_padn + 2.)
    if not fix: stack(xpad, y_padn, 4, 5, 3)
    box(M[5], xpad - 2., y_padn, xpad + 2., y_padn + (y_padp - 414.))
    # shared nets: the two legs' M4 trunks joined straight across the channel; port nets get an M5 strap to the side edge
    # (crossing at the leg trunk's own width for the current-carrying nets: TERM_VCM carries the differential
    # termination current between the legs, ~44 squares of M4 here)
    for net in SHARED:
        w = {'VSS': 2., 'TERM_VCM': 1.}.get(net, .5)
        wire(4, (tr(net), p_top - 1.), (tr(net), n_top + 1.), w)
        if net != 'RAILPRE':     # internal node: no strap, no label
            if not (fix and net == 'TERM_VCM'): stack(tr(net), level[net], 4, 5)
            box(M[5], tr(net), level[net] - .5, xedge, level[net] + .5); T(net, 5, xedge - .5, level[net])
    # RX_P / RX_N: mirror-identical routes (P/N balance at the CTLE input): RX trunk -> 18 um M4 extension into the
    # channel -> 0.6 um M5 strap to the cell's side edge = adjacent side pins, RXSEP apart
    for y_leg, y, net in ((p_top - 1., y_rxp, 'RX_P'), (n_top + 1., y_rxn, 'RX_N')):
        wire(4, (tr('RX'), y_leg), (tr('RX'), y), 1.); stack(tr('RX'), y, 4, 5)
        box(M[5], tr('RX'), y - .3, xedge, y + .3); T(net, 5, xedge - .5, y)
    # RAILPRE / VSS: from the P-leg bank down to the shell exactly as the side-by-side build
    xr = tr('RAILPRE'); ylo = Y_PLEG + cfg['railpre_lo'] + 1.
    wire(4, (xr, ylo), (xr, 436.5), .5); stack(xr, 436.5, 3, 4)
    wire(3, (xr, 436.5), (91.58, 436.5), .5); wire(3, (91.58, 436.25), (91.58, 438.4), .5)
    xv = tr('VSS'); yv = Y_PLEG + cfg['vss_lo'] + 1.
    if cfg.get('sec'):          # --sec: the taller leg covers y 428 in its bank: the strap runs below the leg and rises at x 138
        ys = 406.5              # free Metal3 / Metal4 corridor; joins the shell's Metal5 VSS return vertical (x 136.5-139.5) there
        if Y_PLEG < ys + 4.: raise ValueError('--sec: leg reaches below the VSS strap')
        wire(4, (xv, yv), (xv, ys), 2.); stack(xv, ys, 3, 4, 2)
        wire(3, (xv, ys), (138., ys), 1.); stack(138., ys, 3, 5, 2)
    else:
        wire(4, (xv, yv), (xv, 428.), 2.); stack(xv, 428., 3, 4, 2)
        wire(3, (xv, 428.), (138., 428.), 1.); stack(138., 428., 3, 5, 2)
    if fix:
        def varray(v, x1, y1, x2, y2, skip=None, pitch=.7):       # via cuts on a 0.7 um grid inside the box, >= 0.2 um from its edges
                                                                  # (V4.2b: cuts of arrays larger than 3 x 3 need 0.36 um spacing)
            nx = int((x2 - x1 - .4 - .26) / pitch) + 1; ny = int((y2 - y1 - .4 - .26) / pitch) + 1
            x0 = (x1 + x2) / 2 - (nx - 1) * pitch / 2; y0 = (y1 + y2) / 2 - (ny - 1) * pitch / 2
            for i in range(nx):
                for j in range(ny):
                    cx, cy = x0 + i * pitch, y0 + j * pitch
                    if skip and abs(cx - skip[0]) < 1e-6 and abs(cy - skip[1]) < 1e-6: continue
                    box(V[v], cx - .13, cy - .13, cx + .13, cy + .13)
        # TERM_VCM: wide Metal4 trunk between the leg straps (the channel's Metal5 belongs to the pin straps), pin tap on the midline
        s1, s2 = X + fix['vcm_strap'][0], X + fix['vcm_strap'][1]; mid = (p_top + n_top) / 2; lv = level['TERM_VCM']
        xf = s2 - 4.5                                   # finger: 4.5 um wide, 2.5 um right of the trunk
        box(M[4], s1, p_top - 1., xf - 2.5, n_top + 1.)
        box(M[4], xf - 2.5, mid - 1.5, xf, mid + 1.5)   # bridge at the midline: the only connection of the finger
        box(M[4], xf, mid - 1.5, s2, lv + .8)
        box(M[5], xf, lv - .8, s2, lv + .8); varray(4, xf, lv - .8, s2, lv + .8)
        # shell PAD exits: Metal4 trunk under the Metal5 trunk, one cut each in the shell -> arrays around that cut
        for cx, cy in ((288., 416.), (304., 432.)):
            varray(4, cx - 6., cy - 6., cx + 6., cy + 6., skip=(cx, cy))
        esd_overlays(box, M, V, varray, opt=dict(ESD_OPT, **cfg.get('esd_opt', {})), core_array=cfg.get('core_array', True))
        if not cfg.get('core_array', True):
            # the network ties its rail bleed to the array's Metal3 rail bus (x 129-131, y 443-677) with a Via2 at (130, 458.765):
            # keep the first 16 um of that bus so the bleed stays on ESD_RAIL and the cut keeps its Metal3 landing
            box(M[3], 129., 443., 131., 459.3)
    if cfg.get('site_primary') is not None:
        if not fix: raise ValueError('--site-primary needs the R-fixed leg (the VSS strips of esd_overlays)')
        import pad_site_primary as sp
        sp.load_primitives(l, work)
        sites = {}
        for x0, pad in ((0., 'PAD_P'), (211., 'PAD_N')):
            info = sp.draw(l, root, x0, dict(sp.OPT, **cfg['site_primary']))
            T('DVDD', 3, *info['dvdd_label']); sites[pad] = info
        (work / 'site-primary.json').write_text(json.dumps(sites, indent=1) + '\n')
    if cfg.get('sec'):
        # --sec: DVDD of the legs' secondary diodes -> N site DVDD bar (module docstring). Metal4 / Metal2 only in the shell-free
        # area x 258..320, y 148.7..404 (checked empty in a4); Via2 / Via3 only above the rail cell (y > 348.4).
        xd = tr('DVDD'); yd = Y_PLEG + cfg['dvdd_lo']
        wire(4, (xd, p_top - 1.), (xd, n_top + 1.), 2.)                    # legs joined across the channel
        box(M[4], 311.5, 398., xd + 1., yd + 1.)                          # wide drop beside the P leg (left of its bbox)
        box(M[4], 258., 398., 311.5, 404.)                                 # west along y 398-404
        box(M[4], 258., 352., 282., 404.)                                  # down the N site column
        box(M[3], 258., 352., 282., 362.); box(M[2], 258., 148., 282., 362.)
        varray(3, 258., 352., 282., 362.); varray(2, 258., 352., 282., 362.)
        # reinforcement beside the legs (x 311.5 .. trunk): the N leg's diodes are fed through both legs' 2 um trunks otherwise.
        # Metal4 from the drop up to the N leg's DVDD track, Metal5 over it between the PAD_P (y 414-418) and PAD_N (y 736.23-740.23)
        # Metal5 crossings, Via4 array; Metal3 stubs + Via3 arrays where each leg's DVDD channel track meets its trunk (2 cuts in the leg).
        yP, yN = Y_PLEG + cfg['dvdd_lo'], Y_NLEG - cfg['dvdd_lo']
        box(M[4], 311.5, 398., xd - 1., yN + 1.)
        box(M[5], 312., 419., xd + .4, 735.5); varray(4, 312., 419., xd + .4, 735.5)
        for yt in (yP, yN):
            box(M[3], 311.5, yt - 1., xd - 1., yt + 1.); varray(3, 311.5, yt - 1., xd - 2.2, yt + 1.)   # clear of the leg's own cuts (trunk <= 3.4 um)
    T('PAD_P', 5, 288., 905.); T('PAD_N', 5, 304., 905.)
    T('ESD_RAIL', 3, 130., 444.)
    import marker_merge
    (work / 'marker-merge.json').write_text(json.dumps(marker_merge.merge(l, root), indent=1) + '\n')
    for c in l.each_cell():
        if c.cell_index() != root.cell_index() and not c.name.startswith('svhspad__'):
            c.name = 'svhspad__' + c.name
    o = k.SaveLayoutOptions(); o.add_cell(root.cell_index()); l.write(str(work / 'pad_hspad.gds'), o)
    b = root.dbbox(); (work / 'geometry.json').write_text(json.dumps(dict(bbox_um=[b.left, b.bottom, b.right, b.top], area_um2=b.width() * b.height())) + '\n')


def generate(work, shell, leg, network, stacked=False, site_primary=None, core_array=True, esd_opt=None, sec=False):
    sys.path.insert(0, str(HERE))
    from layout import magic, IMAGE
    from run_first_pass import lvs
    work.mkdir(parents=True, exist_ok=False)
    shutil.copy(shell / 'pad.gds', work / 'shell.gds'); shutil.copy(leg / 'pt_hs_leg.gds', work / 'leg.gds')
    for f in ('marker_merge.py',):
        shutil.copy(HERE / f, work / f)
    shutil.copy(Path(__file__), work / 'hs_pad_compose.py')
    if site_primary is not None:
        import pad_site_primary as sp
        shutil.copy(HERE / 'pad_site_primary.py', work / 'pad_site_primary.py')
        for n in (sp.ND, sp.PD): shutil.copy(sp.PRIM / f'{n}.gds', work / f'{n}.gds')
    # leg trunk geometry from its labels (convkit bank, x < 0)
    q = ('import klayout.db as k,json\nl=k.Layout();l.read("/work/leg.gds");t=l.top_cell();out={}\n'
         'for li in l.layer_indexes():\n for s in t.each_shape(li):\n  if s.is_text():out.setdefault(s.text_string,[]).append([s.dtext.x,s.dtext.y,l.get_info(li).datatype])\n'
         'b=t.dbbox();print(json.dumps(dict(labels=out,bbox=[b.left,b.bottom,b.right,b.top])))\n')
    (work / 'q.py').write_text(q)
    r = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--mount', f'type=bind,src={work},dst=/work', IMAGE, '/work/q.py'], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout.strip().splitlines()[-1])
    lab = info['labels']
    tx = {n: v[0][0] for n, v in lab.items() if not n.startswith('TU')}
    if ('DVDD' in tx) != bool(sec):
        raise ValueError('--sec needs a leg built with hs_leg_layout.py --sec (DVDD port), and such a leg needs --sec')
    lo = lambda n: min(p[1] for p in lab[n] if p[2] == 0)
    cfg = dict(trunk_x=tx, leg_top=info['bbox'][3], leg_right=info['bbox'][2], pad_trunk_lo=lo('PAD'), railpre_lo=lo('RAILPRE'), vss_lo=lo('VSS'), stacked=stacked)
    if sec:
        if site_primary is None: raise ValueError('--sec is only allowed with --site-primary')
        cfg.update(sec=True, dvdd_lo=lo('DVDD'))
    linfo = json.loads((leg / 'layout-info.json').read_text()) if (leg / 'layout-info.json').exists() else {}
    if linfo.get('r_fix'):
        if not stacked: raise ValueError('the R-fixed leg is only composed in the stacked build')
        cfg['r_fix'] = linfo['r_fix']
    if site_primary is not None:
        if not cfg.get('r_fix'): raise ValueError('--site-primary needs the R-fixed leg')
        cfg['site_primary'] = dict(sp.OPT, **site_primary)
    if not core_array:
        if site_primary is None: raise ValueError('--no-core-array is only allowed with --site-primary')
        cfg['core_array'] = False
    if esd_opt:
        if not cfg.get('r_fix') or set(esd_opt) - set(ESD_OPT): raise ValueError('--esd-opt: R-fixed leg only, keys of ESD_OPT only')
        cfg['esd_opt'] = esd_opt
    (work / 'config.json').write_text(json.dumps(cfg, indent=1))
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--mount', f'type=bind,src={work},dst=/work', IMAGE,
                    '/work/hs_pad_compose.py', '--inside', '/work'], check=True)
    (work / 'extract.tcl').write_text('crashbackups stop\ngds read pad_hspad.gds\nload pad_hspad\nselect top cell\nflatten pad_hspad_flat\nload pad_hspad_flat\nsave\nselect top cell\nexpand\n'
        'drc check\ndrc catchup\nputs "HS_DRC [drc list count total]"\nputs [drc listall why]\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nquit -noprompt\n')
    res = magic(work, 'extract.tcl')
    m = re.search(r'HS_DRC (\d+)', res.stdout)
    drc = int(m[1]) if m else None
    raw = (work / 'pad_hspad_flat.spice').read_text()
    ports = next(line.split()[2:] for line in re.sub(r'\n\+\s*', ' ', raw).splitlines() if line.startswith('.subckt'))
    shell_ref = (shell / 'reference.spice').read_text()
    if not core_array:       # the array's steering diodes leave the reference: D<n> VSS PAD? nd2ps / D<n> PAD? RAIL pd2nw
        keep = [x for x in shell_ref.splitlines() if not re.match(r'D\d+ (VSS PAD[PN]|PAD[PN] RAIL) diode_(nd2ps|pd2nw)_06v0 ', x)]
        if len(shell_ref.splitlines()) - len(keep) != 24: raise ValueError('expected 24 array diodes in the shell reference')
        shell_ref = '\n'.join(keep) + '\n'
    leg_ref = (leg / 'pt_hs_leg.lvs_sch.spice').read_text()
    top = ('.subckt hs_reference ' + ' '.join(ports) + '\n'
           'XSH PAD_N PAD_P VSS ESD_RAIL RAILPRE pad_reference\n'
           'XLP PAD_P RX_P VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0 TERM_TRIM1 TERM_TRIM2 TERM_TRIM3 VDD VSS RAILPRE' + (' DVDD' if sec else '') + ' pt_hs_leg\n'
           'XLN PAD_N RX_N VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0 TERM_TRIM1 TERM_TRIM2 TERM_TRIM3 VDD VSS RAILPRE' + (' DVDD' if sec else '') + ' pt_hs_leg\n' +
           ''.join(x + '\n' for pad in ('PAD_P', 'PAD_N') for x in (sp.reference_lines('S' + pad[-1], pad, 'VSS', 'DVDD', cfg['site_primary']) if site_primary is not None else [])) +
           '.ends hs_reference\n')
    strip = lambda t: '\n'.join(x for x in t.splitlines() if not x.startswith('C')) + '\n'
    (work / 'reference.spice').write_text(strip(shell_ref + leg_ref + top)); (work / 'actual.spice').write_text(strip(raw))
    ok = lvs(work, 'actual.spice', 'pad_hspad_flat', 'reference.spice', 'hs_reference', 'pad-lvs.txt')
    # simulation model: same array-well correction as the shell (network-with-well DWELL_ARRAY)
    manifest = json.loads((network / 'network-layout.json').read_text())
    corr = manifest['array_well_capacitance_removed_ff']; lines = raw.splitlines(); n = 0
    for i, line in enumerate(lines if core_array else []):     # no array, no array wells: nothing to correct
        t = line.split()
        if t and t[0].startswith('C') and set(t[1:3]) == {'VSS', 'ESD_RAIL'}:
            v = float(t[3][:-1]) * {'f': 1., 'p': 1000.}[t[3][-1]]
            if v <= corr: raise ValueError('well correction exceeds extracted C')
            lines[i] = ' '.join(t[:3]) + f' {v - corr:.9g}f'; n += 1
    well = next(x for x in (network / 'network-with-well.spice').read_text().splitlines() if x.startswith('DWELL_ARRAY')).replace(' RAIL ', ' ESD_RAIL ')
    physical = ('\n'.join(lines).replace('.ends', well + '\n.ends') if core_array else '\n'.join(lines)) + '\n'
    public = [p for p in ports if p not in ('ESD_RAIL', 'RAILPRE')]
    wrapper = '.subckt hs_protected_pad ' + ' '.join(public) + '\nXPHYSICAL ' + ' '.join(ports) + ' pad_hspad_flat\n.ends hs_protected_pad\n'
    (work / 'physical.spice').write_text(wrapper + physical)
    from protection_device_audit import check
    aud = check(work / 'pad_hspad_flat.ext', work / 'physical.spice', work / 'independent-device-audit.json', work / 'pad_hspad_flat.spice' if core_array else None,
                **(dict(ring_wells=('DVDD',)) if site_primary is not None else {}))
    rep = dict(status='hs_pad_composed', drc_count=drc, lvs_match=bool(ok), well_corrections=n, independent_device_graph_match=aud['device_graph_matches'],
               ports=public, geometry=json.loads((work / 'geometry.json').read_text()), config=cfg,
               source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), shell / 'pad.gds', leg / 'pt_hs_leg.gds', network / 'network-layout.json') +
                              ((HERE / 'pad_site_primary.py',) if site_primary is not None else ())})
    (work / 'layout-screen.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({k: rep[k] for k in ('drc_count', 'lvs_match', 'well_corrections', 'independent_device_graph_match', 'geometry')}))


if __name__ == '__main__':
    if sys.argv[1] == '--inside':
        assemble(Path(sys.argv[2]))
    else:
        sp_opt = None; e_opt = None
        for a in sys.argv[5:]:
            if a.startswith('--esd-opt='): e_opt = json.loads(a.split('=', 1)[1])
            if a == '--site-primary': sp_opt = {}
            elif a.startswith('--site-primary='): sp_opt = json.loads(a.split('=', 1)[1])
        generate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), Path(sys.argv[4]).resolve(),
                 stacked='--stacked' in sys.argv[5:], site_primary=sp_opt, core_array='--no-core-array' not in sys.argv[5:], esd_opt=e_opt,
                 sec='--sec' in sys.argv[5:])
