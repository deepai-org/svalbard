#!/usr/bin/env python3
"""pad_txpad rework (2026-11-18, UNPUBLISHED candidate): hand-placed wired-transmit pad with a low-resistance
output path, a trimmed termination and pad-site primary diodes on the ring rails (ESD option A).

    python3 tx_pad_layout.py <empty work dir> [--part drv|leg|all] [--main-scale 0.6] [--post-scale S] [--tmds-scale S]

Everything is drawn flat in one Magic cell from PDK PCells (no row router), mirror-symmetric about x = AXIS:
  driver  8 unit tiles stacked in y.  Tile, left to right: 2 x cascode nfet_06v0 16/0.7 (PAD_P) | TMDS_P POST_P MAIN_P
          switches (nfet_03v3 W/0.28) | tails nfet_03v3 20/1 as nf=2 cells: MAIN POST TMDS POST MAIN | MAIN_N POST_N
          TMDS_N | 2 x cascode (PAD_N).  Every source / drain column: widened Metal1 + Metal2 with a via1 column.
          Unit nets on three Metal3 bands across the tile (A: SUM_x_D_u and MAIN_TAIL_u, B: POST_TAIL_u,
          C: TMDS_TAIL_u), via2 columns at the crossings.  PAD_x: Metal4 + Metal5 bus over the cascodes.  VSS:
          Metal1 rung above every tile (all guard rings, tail sources), Metal4 + Metal5 bus over the tails.  Gate
          nets: 0.38 um Metal2 lines over the shared guard-ring columns.
  legs    termination, per leg N_BASE base units (ppolyf_u 2 x LB + nfet_03v3 WB/0.28, gate TERM_ENABLE_LOCAL) and 15
          trim units (2 x LT + WT/0.28, gates TERM_TRIM0..3 = 1/2/4/8 units).  Resistor heads sit directly under the
          PAD_x bus (Metal3-5); switch sources on a Metal3 + Metal4 TERM_VCM bus shared by both legs.
  pad     bond pad (provider Bondpad_5LM), primary diodes in the pad site (4 x nd2ps to DVSS_x, 4 x pd2nw to DVDD_x, the
          pad_tlp_flat pattern, via2 onto the ring's Metal3), Metal2-only neck NECK_W wide through the ring band.
  VSS     core ground lands on the innermost ring DVSS band (depth 342-348.39) on Metal3-5.
Options default to the candidate; --main-scale etc. are the 0.6x MAIN switch option (default OFF = 20 um switches).
--sec=JSON (candidate a5, 2026-11-20; default OFF = the a4 cell, unchanged): LOCAL SECONDARY CLAMP at the termination switch drains.
  Per leg a diode row between the switch and resistor rows (the resistor row and everything above it move up by the row height):
  one n-well strip along the leg (cathode, n+ tap strip with Metal1 on top), per unit one p+ island (diode_pd2nw_06v0, anode) under
  the unit's TU Metal2 riser (via1), i.e. behind the unit's poly. Cathode net DVDDS_<leg> (new port): Metal3 + Metal4 bus over the
  row, via stacks in the Metal2 channels between units; the channels inside the pad-site x range continue down on Metal2 to a plate
  that lands (Via2 + Metal3 pads) on the ring DVDD sub-bands 206-213 / 214-229 / 262-269 / 270-277 / 278-285 / 294-301 / 334-341 of the rail tile (no Metal2 there).
  The switch guard-ring Metal1 columns are dropped (they would cross the row); the switch rings are chained along their bottom bars
  and tied to the VSS column at the axis. JSON keys: "an": [w, l] um p+ island (default [0.8, 1.5]).
--sw6=JSON (candidate a6, 2026-11-20; default OFF = the a4 cell, unchanged): termination switches nfet_06v0 (coordinator ruling: 6 V devices,
  static). JSON keys: "w" switch width um (all 23 units per leg, nf=1, L 0.7; default 66), "lb" / "lt" poly length of the base / trim units
  (default 2.0 / 1.0). The taller switch row pushes the resistor row, the PAD buses, the driver and the control cell up by the extra height
  (rounded up to 0.5 um); the bond pads, the pad sites and the ring landings stay where they are.
  "upx": site-local x of extra pd2nw fingers (PAD -> DVDD) in a row at depth "yu" (default 107) right of the neck, between the bond pad
  and the first diode row (coordinator ruling: more primary area if the 6 V cascodes exceed 8.0 V at CDM 2 A); default none.
  "bufp": width of TERM_BUF_P (pfet_06v0, L 0.55) in pt_tx_ctl, default 40 (published 4): the 6 V switches run at 0.1-0.3 V overdrive at
  ss / 3.15 V, the 4 um buffer's 80 mV drop into the bleed chain doubled the base-unit resistance there.
  (a6, ABANDONED 2026-11-20: ruling withdrawn; kept out of the default path for the record.)
--upx=JSON (candidate a7; default OFF): a6's extra pd2nw row with the 3.3 V termination: {"x": [57, 63, 69], "yu": 107}.
--nvt=JSON (candidate a8, 2026-11-20, coordinator ruling PC-49 (a); default OFF = the a4 cell, unchanged): termination switches native
  nfet_06v0_nvt (6 V, low threshold: gate overdrive at the 1.65 V termination common mode). Keys "wb" / "wt" switch width um of the base /
  trim units (nf=1), "l" switch length (default 1.8 = lmin), "lb" / "lt" poly length of the base / trim resistors. The switch PCell is drawn
  without a guard ring (guard 0; with its ring it is 4.06 um wide vs the 3.56 um resistor pitch): per leg one pwell over the switch row, a
  p-tap strip (Metal1) under it at Y_LEG - 1.1 .. - 0.6, and Metal1 columns on the unit boundaries from the strip to the resistor ring bars.
  The switch row keeps the a4 height (23.16 um) so nothing above the legs moves. Combine with --upx for the extra up-diodes.
  "merged": true (a8/a9): one multi-finger native device per trim bit, each in its own NAT (leg_nat, nat_post).
  "disc": [w, l, nf] (a10, needs --top-pins): series nfet_03v3 disconnect, see disconnect(); the TERM_VCM pin moves to the control-cell trunk.
--top-pins (ASM-2, default OFF): every core-side port on the top (core-facing) edge, flush with y = Y_TOP, Metal3 / Metal4: driver gate lines
  (Metal2) end in a via2 + Metal3 pin; VDD / VSS / TERM_ENABLE / DETECT_* on the control cell's Metal4 trunks; TERM_TRIM0..3 leave their
  Metal3 lines east of the N leg on via3 / via4 into 1 um Metal5 risers (over the TERM_VCM bus) to Metal4 pins; TERM_VCM: a 4 um Metal4
  riser from the TERM_VCM bus at the east edge. East / inner side labels dropped. Not pins: PAD_P / PAD_N, DVDD_P / DVDD_N (ring landings).
"""
import argparse, json, os, subprocess, sys, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent
IMAGE = os.environ.get('SVALBARD_PAD_IMAGE', 'svalbard/librelane-gf180-canary:2026.08')
PDK = '/pdk/gf180mcuD'
PRIM = HERE / 'generated/protection-primitives'
AXIS = 143.            # mirror axis (bond centres 37.5 / 248.5)
N_BASE, LB, WB, LT, WT = 8, 2.0, 20., 2.8, 12.
TRIM_GATES = [f'TERM_TRIM{k}' for k in range(4) for _ in range(1 << k)]
NECK_W = 30.
UP2 = (56.5, 62.5, 68.5)   # second row of up-diodes (site-local x); () = 4 + 4 fingers only
TILE_PITCH, UNITS = 25., 8
BANDS = dict(A=(-4.4, 4.4), B=(4.9, 9.7), C=(-9.7, -4.9))
Y_GATE0 = 353.4        # termination gate lines (5 lines, 0.8 pitch)
Y_LEG = 358.           # switch row bottom (pwell)
Y_DRV0 = 432.          # centre of driver tile 0
CTL_X, CTL_Y = 17., 626.   # origin of the control cell
Y_TOP = CTL_Y + 66.26   # top edge (pins)
TOP_PINS = False        # --top-pins (ASM-2)
RISER_WIDE = False      # --nvt "riser_wide" (a12)
CTL_EARLY = None
DISC_M3 = False         # --nvt "disc_m3" (a16)
DISC = False            # --nvt "disc" (a10): series disconnect between the native banks' source bus (TERM_VCM_BUS) and the TERM_VCM pin
TRIM_RISER_X = (266.5, 269.1, 271.7, 274.3)   # --top-pins: TERM_TRIM0..3 Metal5 risers (centre x)
X_EAST = 2 * AXIS - 3.
q = lambda v: round(round(v / .005) * .005, 4)


def docker_magic(work, script, timeout=3600):
    r = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh', '--user', f'{os.getuid()}:{os.getgid()}',
                        '-e', 'HOME=/tmp', '-v', f'{work}:/work', '-w', '/work', IMAGE, '-c',
                        f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}'],
                       capture_output=True, text=True, timeout=timeout)
    (work / (script + '.log')).write_text(r.stdout + r.stderr)
    return r


def rects(path):
    layer, r = None, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('<< '): layer = line[3:-3]
        if line.startswith('rect '): r.setdefault(layer, []).append([float(v) * .005 for v in line.split()[1:]])
    return r


class Prim:
    """Geometry of one PCell: S/D column centres, their half height, guard-ring columns, gate contacts."""
    def __init__(self, name, path):
        r = rects(path); self.name = name
        dc = next((r[k] for k in ('ndiffc', 'mvndiffc') if k in r), None)
        ring = next((r[k] for k in ('psubdiffcont', 'mvpsubdiffcont') if k in r), None)
        sub = next((r[k] for k in ('psubdiff', 'mvpsubdiff') if k in r), None)
        if ring:
            self.ring_x = max((a[0] + a[2]) / 2 for a in ring)           # +- ring column centre
            self.ring_hw = max(a[2] for a in sub)                         # ring outer half width
            self.ring_top = max(a[3] for a in sub); self.ring_bot = min(a[1] for a in sub)
            self.ring_ctop = max(a[3] for a in ring)
        else: self.ring_x = self.ring_hw = self.ring_top = self.ring_bot = self.ring_ctop = None   # guard 0 (--nvt switches)
        self.pw = r['pwell'][0]
        if dc:
            self.cols = sorted(q((a[0] + a[2]) / 2) for a in dc); self.hh = max(a[3] for a in dc)
            dd = next((r[k] for k in ('mvndiff', 'ndiff') if k in r), dc)
            self.dbox = (min(a[0] for a in dd), min(a[1] for a in dd), max(a[2] for a in dd), max(a[3] for a in dd))   # diffusion (COMP) bbox
            self.gates = sorted(((a[0] + a[2]) / 2, (a[1] + a[3]) / 2) for a in r['polycontact']); self.gate_w = r['polycontact'][0][2] - r['polycontact'][0][0]
        else:                                                         # resistor: heads top / bottom
            pc = sorted(r['polycontact'], key=lambda a: a[1]); self.head_b = (pc[0][1] + pc[0][3]) / 2; self.head_a = (pc[1][1] + pc[1][3]) / 2


class Cell:
    def __init__(self, name):
        self.name = name; self.c = ['crashbackups stop', f'set ::env(PDKPATH) {PDK}', f'path search +{PDK}/libs.ref/gf180mcu_fd_io/mag']
        self.labels = []; self.ninst = 0; self.dev = []
    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((q(x1), q(x2))); y1, y2 = sorted((q(y1), q(y2)))
        self.c += [f'box values {x1} {y1} {x2} {y2}', f'paint {layer}']
    def metal(self, n, x1, y1, x2, y2): self.rect(f'metal{n}', x1, y1, x2, y2)
    def via(self, n, x1, y1, x2, y2): self.rect(f'via{n}', x1, y1, x2, y2)
    def stack(self, lo, hi, x1, y1, x2, y2, enc=.1):
        """metal lo..hi over the box, via areas inset by enc."""
        for m in range(lo, hi + 1): self.metal(m, x1, y1, x2, y2)
        for m in range(lo, hi): self.via(m, x1 + enc, y1 + enc, x2 - enc, y2 - enc)
    def inst(self, prim, x, y, name):
        self.c += [f'getcell {prim} child 0 0 parent {q(x)} {q(y)}', f'identify X{name}']; self.ninst += 1
    def label(self, net, x, y, layer, port=False):
        self.labels.append((net, q(x), q(y), layer, port))


def make_prims(work, widths, sw6=None, nvt=None):
    spec = dict(cas=('nfet_06v0', 16., .7, 1), tail2=('nfet_03v3', 20., 1., 2), tsb=('nfet_03v3', WB, .28, 1), tst=('nfet_03v3', WT, .28, 1))
    if sw6: spec.update(tsb=('nfet_06v0', sw6['w'], .7, 1), tst=('nfet_06v0', sw6['w'], .7, 1))
    if nvt: spec.update(tsb=('nfet_06v0_nvt', nvt['wb'], nvt['l'], 1), tst=('nfet_06v0_nvt', nvt['wt'], nvt['l'], 1))
    if nvt and nvt.get('merged'):     # one multi-finger native device per trim bit: base N_BASE fingers, bit k 2^k fingers
        del spec['tsb'], spec['tst']
        spec['nvB'] = ('nfet_06v0_nvt', nvt['wb'], nvt['l'], N_BASE)
        for k in range(4): spec[f'nvT{k}'] = ('nfet_06v0_nvt', nvt['wt'], nvt['l'], 1 << k)
        if nvt.get('disc'): spec['dis'] = ('nfet_03v3', nvt['disc'][0], nvt['disc'][1], nvt['disc'][2])
        if nvt.get('disc2'): spec['dis'] = ('nfet_03v3', nvt['disc2'][0], nvt['disc2'][1], nvt['disc2'][2])
    for b, w in widths.items(): spec['sw_' + b] = ('nfet_03v3', w, .28, 1)
    res = dict(rb=sw6['lb'], rt=sw6['lt']) if sw6 else dict(rb=nvt['lb'], rt=nvt['lt']) if nvt else dict(rb=LB, rt=LT)
    c = ['crashbackups stop', 'load primitive_workspace']
    for n, (model, w, l, nf) in spec.items():
        gd = 0 if model == 'nfet_06v0_nvt' else 1
        tb = 'topc 1 botc 0' if (n == 'dis' and nvt and nvt.get('disc2')) else 'topc 0 botc 1'
        c += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf {nf} guard {gd} {tb} full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
              'load $cell', f'save txp_{n}', 'load primitive_workspace']
    for n, l in res.items():
        c += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::ppolyf_u w 2 l {l} guard 1 full_metal 1]', 'load $cell', f'save txp_{n}', 'load primitive_workspace']
    (work / 'prims.tcl').write_text('\n'.join(c + ['quit -noprompt']) + '\n')
    docker_magic(work, 'prims.tcl')
    P = {n: Prim(n, work / f'txp_{n}.mag') for n in list(spec) + list(res)}
    for n, v in spec.items(): P[n].w_f, P[n].l_ = v[1], v[2]
    return P, spec


def sd_column(C, x, y, hh, m2_hh=None, via=True):
    """Widened Metal1 + Metal2 with a via1 column over one source / drain contact column centred (x, y)."""
    C.metal(1, x - .23, y - hh + .03, x + .23, y + hh - .03)
    m2 = m2_hh or hh
    C.metal(2, x - .2, y - hh, x + .2, y + m2)
    if via: C.via(1, x - .13, y - hh + .2, x + .13, y + hh - .2)


def gate_jog(C, P, x, y, xline, yj=None):
    """Gate contact(s) of the device at (x, y): via1 on each contact, Metal2 bar at the contact height across the guard ring
    to the Metal2 gate line at xline (the PCell ring is closed, so the gate leaves on Metal2)."""
    gy = P.gates[0][1]
    for gx, _ in P.gates:
        hw = max(.19, (P.gate_w - .1) / 2)
        C.metal(1, x + gx - hw, y + gy - .19, x + gx + hw, y + gy + .19)
        C.via(1, x + gx - hw + .06, y + gy - .13, x + gx + hw - .06, y + gy + .13)
    hw = max(.19, (P.gate_w - .1) / 2)
    xs = [x + g[0] - hw for g in P.gates] + [x + g[0] + hw for g in P.gates] + [xline - .19, xline + .19]
    C.metal(2, min(xs) - .01, y + gy - .2, max(xs) + .01, y + gy + .2)


def driver(C, P, ox, oy, sch, line_top=None):
    """8 unit tiles centred x = ox, tile u centred y = oy + u * TILE_PITCH. Returns the gate-line x positions and bus boxes."""
    cas, t2 = P['cas'], P['tail2']
    sw = {b: P['sw_' + b] for b in ('MAIN', 'POST', 'TMDS')}
    # --- x placement of the left half (negative x), mirrored for the right half
    tails = ['MAIN', 'POST', 'TMDS', 'POST', 'MAIN']
    tp = 2 * t2.ring_hw - .36
    tx = [q((i - 2) * tp) for i in range(5)]
    xs = {}; x = tx[0] - t2.ring_hw
    for b in ('MAIN', 'POST', 'TMDS'):
        x = x + .36 - sw[b].ring_hw; xs[b] = q(x); x -= sw[b].ring_hw
    x -= 1.6
    xcb = q(x - cas.ring_hw); xca = q(xcb - 2 * cas.ring_hw + .36)
    hw = q(-(xca - cas.ring_hw) + .4)                               # tile half width
    lines = {}                                                      # gate net -> list of line x (relative)
    def line(net, x): lines.setdefault(net, []).append(q(x))
    line('CASCODE', (xca + xcb) / 2); line('CASCODE', -(xca + xcb) / 2)
    line('TMDS_P', xs['TMDS'] - sw['TMDS'].ring_x); line('TMDS_N', -(xs['TMDS'] - sw['TMDS'].ring_x))
    line('POST_P', xs['POST'] - sw['POST'].ring_x); line('POST_N', -(xs['POST'] - sw['POST'].ring_x))
    line('MAIN_P', xs['MAIN'] - sw['MAIN'].ring_x); line('MAIN_N', -(xs['MAIN'] - sw['MAIN'].ring_x))
    for i, b in enumerate(tails): line(b + '_BIAS', tx[i] - t2.ring_x if i < 3 else tx[i] + t2.ring_x)
    ybot = oy - 12.2; ytop = oy + (UNITS - 1) * TILE_PITCH + 13.2
    for net, xl in lines.items():
        for xx in xl: C.metal(2, ox + xx - .19, ybot, ox + xx + .19, line_top or ytop + 4.5)
    bx = dict(pad=(xca - cas.ring_hw - 10., xcb + cas.ring_hw - .2), vss=(tx[0] - t2.ring_x + .6, tx[4] + t2.ring_x - .6))
    for u in range(UNITS):
        y = oy + u * TILE_PITCH
        rung = (y + 11.0, y + 12.8)
        C.metal(1, ox - hw, rung[0], ox + hw, rung[1])
        for s, leg in ((1, 'P'), (-1, 'N')):                         # s = +1: left half as computed, -1: mirrored
            X = lambda v: ox + s * v
            other = 'N' if leg == 'P' else 'P'
            # cascodes: A (outer): drain outer column, source inner; B: source outer (towards A), drain inner
            for k, xc in enumerate((xca, xcb)):
                C.inst('txp_cas', X(xc), y, f'CAS_{leg}_{u}_{k}')
                d, sr = (cas.cols[0], cas.cols[1]) if k == 0 else (cas.cols[1], cas.cols[0])
                sch.append((f'CAS_{leg}_{u}_{k}', f'PAD_{leg}', 'CASCODE', f'SUM_{leg}_D_{u}', 'VSS', 'nfet_06v0', 16., .7))
                for col in (d, sr): sd_column(C, X(xc + col), y, cas.hh)
                C.via(2, X(xc + sr) - .14, y + BANDS['A'][0] + .1, X(xc + sr) + .14, y + BANDS['A'][1] - .1)
                for ya, yb in ((5.0, 7.7), (-7.7, -5.0)):            # drain -> Metal3 pad -> PAD bus (Metal4/5)
                    C.metal(3, X(xc + d) - .5, y + ya, X(xc + d) + .5, y + yb)
                    C.via(2, X(xc + d) - .14, y + ya + .1, X(xc + d) + .14, y + yb - .1)
                    C.via(3, X(xc + d) - .4, y + ya + .1, X(xc + d) + .4, y + yb - .1)
                for rx in (-cas.ring_x, cas.ring_x):                 # ring columns up to the rung
                    C.metal(1, X(xc + rx) - .115, y + cas.ring_ctop - .3, X(xc + rx) + .115, rung[0] + .2)
            gate_jog(C, cas, X(xca), y, X((xca + xcb) / 2))
            gate_jog(C, cas, X(xcb), y, X((xca + xcb) / 2), cas.ring_bot - .3)
            # switches: drain = outer column (towards the cascodes), source = inner column
            band_of = dict(MAIN='A', POST='B', TMDS='C')
            for b in ('MAIN', 'POST', 'TMDS'):
                p = sw[b]; xc = xs[b]
                C.inst('txp_sw_' + b, X(xc), y, f'{b}_{leg}_SEL_{u}')
                sch.append((f'{b}_{leg}_SEL_{u}', f'SUM_{leg}_D_{u}', f'{b}_{leg}', f'{b}_TAIL_{u}', 'VSS', 'nfet_03v3', p.hh * 2 + .13, .28))
                for col in p.cols: sd_column(C, X(xc + col), y, p.hh, m2_hh=9.9)
                C.via(2, X(xc + p.cols[0]) - .14, y + BANDS['A'][0] + .1, X(xc + p.cols[0]) + .14, y + BANDS['A'][1] - .1)
                ya, yb = BANDS[band_of[b]]
                C.via(2, X(xc + p.cols[1]) - .14, y + max(ya, -p.hh) + .1, X(xc + p.cols[1]) + .14, y + yb - .1)
                gate_jog(C, p, X(xc), y, X(xc - p.ring_x), -11.4)
                if p.ring_ctop < 10.8:                               # narrow (resized) switch: tie its ring to the rung
                    for rx in (-p.ring_x, p.ring_x): C.metal(1, X(xc + rx) - .115, y + p.ring_ctop - .3, X(xc + rx) + .115, rung[0] + .2)
            # SUM band (A) from the outer cascode source to the MAIN switch drain
            C.metal(3, X(xca + cas.cols[1]) - s * .2, y + BANDS['A'][0], X(xs['MAIN'] + sw['MAIN'].cols[0]) + s * .2, y + BANDS['A'][1])
            C.label(f'SUM_{leg}_D_{u}', X(xcb), y, 'metal3')
        # tails
        for i, b in enumerate(tails):
            xc = ox + tx[i]
            C.inst('txp_tail2', xc, y, f'{b}_TAIL_{u}_{i}')
            for f in range(2): sch.append((f'{b}_TAIL_{u}_{i}{f}', f'{b}_TAIL_{u}', f'{b}_BIAS', 'VSS', 'VSS', 'nfet_03v3', 20., 1.))
            sd_column(C, xc + t2.cols[1], y, t2.hh)
            ya, yb = BANDS[dict(MAIN='A', POST='B', TMDS='C')[b]]
            C.via(2, xc + t2.cols[1] - .14, y + ya + .1, xc + t2.cols[1] + .14, y + yb - .1)
            for col in (t2.cols[0], t2.cols[2]):                     # sources: column + extension up to the rung
                sd_column(C, xc + col, y, t2.hh)
                C.metal(1, xc + col - .23, y + t2.hh - .1, xc + col + .23, rung[0] + .2)
                C.metal(2, xc + col - .2, y + t2.hh - .1, xc + col + .2, rung[1] - .1)
            gate_jog(C, t2, xc, y, xc + (-t2.ring_x if i < 3 else t2.ring_x), -11.4)
        # tail bands: MAIN_TAIL (A), POST_TAIL (B), TMDS_TAIL (C) between the two switches' source columns
        for b, band in (('MAIN', 'A'), ('POST', 'B'), ('TMDS', 'C')):
            xe = -(xs[b] + sw[b].cols[1]) + .2
            C.metal(3, ox - xe, y + BANDS[band][0], ox + xe, y + BANDS[band][1])
            C.label(f'{b}_TAIL_{u}', ox, y + sum(BANDS[band]) / 2, 'metal3')
        # VSS rung -> bus: Metal2..4 pads between the gate lines over the tails
        edges = [tx[0] - t2.ring_x] + [tx[i] + t2.ring_x for i in (0, 1)] + [tx[i] - t2.ring_x for i in (3, 4)] + [tx[4] + t2.ring_x]
        edges = sorted(set(q(e) for e in edges))
        for a, b_ in zip(edges[:-1], edges[1:]):
            C.stack(1, 4, ox + a + .5, rung[0] + .1, ox + b_ - .5, rung[1] - .1)
    y1, y2 = oy - 12., oy + (UNITS - 1) * TILE_PITCH + 12.8
    C.metal(4, ox + bx['vss'][0], y1, ox + bx['vss'][1], y2); C.metal(5, ox + bx['vss'][0], y1, ox + bx['vss'][1], y2)
    C.via(4, ox + bx['vss'][0] + .5, y1 + .5, ox + bx['vss'][1] - .5, y2 - .5)
    for s in (1, -1):
        a, b_ = sorted((ox + s * bx['pad'][0], ox + s * bx['pad'][1]))
        C.metal(4, a, y1, b_, y2); C.metal(5, a, y1, b_, y2); C.via(4, a + .5, y1 + .5, b_ - .5, y2 - .5)
    return dict(lines=lines, bus=bx, hw=hw, y=(y1, y2), ytop=line_top or ytop + 4.5)


def sec_row(sec):
    """--sec diode row: (p+ island w, l, nwell bottom offset above the base switch pwell, nwell height, row height added)."""
    w, l = sec.get('an', [.8, 1.5])
    hn = .6 + l + 1. + .5 + .3                                               # p+ enclosure, island, p+ - n+ gap (implant clearance), tap, tap enclosure
    return w, l, .6, hn, .6 + hn + .6 - .3


def leg(C, P, x0, s, name, sch, sec=None, sw6=None, nvt=None):
    """Termination leg `name` (P / N): unit k centred x0 + s * k * pitch. Returns geometry of its buses."""
    if nvt and nvt.get('merged'): return leg_nat(C, P, x0, s, name, sch, nvt)
    rb, rt, sb, st = P['rb'], P['rt'], P['tsb'], P['tst']
    pitch = q(2 * rb.ring_hw - .36)
    gates = ['TERM_ENABLE_LOCAL'] * N_BASE + TRIM_GATES
    gy = {g: q(Y_GATE0 + .8 * i) for i, g in enumerate(['TERM_ENABLE_LOCAL'] + [f'TERM_TRIM{k}' for k in range(4)])}
    ytop = Y_LEG + (sb.pw[3] - sb.pw[1]) + .3 + (rb.pw[3] - rb.pw[1])      # resistor row top (pwell), same for both unit kinds
    if sw6: ytop = Y_LEG + max(sb.pw[3] - sb.pw[1], st.pw[3] - st.pw[1]) + .3 + max(rb.pw[3] - rb.pw[1], rt.pw[3] - rt.pw[1])
    if nvt and nvt.get('merged'): return leg_nat(C, P, x0, s, name, sch, nvt)
    if nvt:     # switch row keeps the a4 height (23.16) so the resistor row and everything above stay put
        ytop = Y_LEG + max(23.16, sb.pw[3] - sb.pw[1], st.pw[3] - st.pw[1]) + .3 + max(rb.pw[3] - rb.pw[1], rt.pw[3] - rt.pw[1])
        assert ytop <= Y_LEG + 23.16 + .3 + 5.18 + .5, ytop    # <= 0.5 um above a4 (386.64): the PAD buses follow, the driver stays
    swm, wb_, wt_, lb_, lt_ = ('nfet_06v0', sw6['w'], sw6['w'], sw6['lb'], sw6['lt']) if sw6 else ('nfet_06v0_nvt', nvt['wb'], nvt['wt'], nvt['lb'], nvt['lt']) if nvt else ('nfet_03v3', WB, WT, LB, LT)
    lsw = .7 if sw6 else nvt['l'] if nvt else .28
    if sec:
        aw, al, n0, hn, dh = sec_row(sec); ytop = q(ytop + dh + max(0., (rt.pw[3] - rt.pw[1]) - (rb.pw[3] - rb.pw[1]))); yrow = Y_LEG + (sb.pw[3] - sb.pw[1]); yn = q(yrow + n0)
        ypa = q(yn + .6); yt = q(ypa + al + 1.); xs_ = []; kx = []
    ya = None
    for k, g in enumerate(gates):
        base = g == 'TERM_ENABLE_LOCAL'; r, w = (rb, sb) if base else (rt, st)
        x = q(x0 + s * (k * pitch + (0. if base else 1.))); ys = q(Y_LEG - w.pw[1]); yr = q(ytop - r.pw[3])   # 1 um between the base and trim groups (ring heights differ)
        tu = f'TU_{name}_{k}'
        C.inst('txp_tsb' if base else 'txp_tst', x, ys, f'TERM_{name}_SW_{k}')
        C.inst('txp_rb' if base else 'txp_rt', x, yr, f'TERM_{name}_R_{k}')
        sch.append((f'TERM_{name}_SW_{k}', tu, g, 'TERM_VCM', 'VSS', swm, wb_ if base else wt_, lsw))
        sch.append((f'TERM_{name}_R_{k}', f'PAD_{name}', tu, 'VSS', 'ppolyf_u', 2., lb_ if base else lt_))
        # switch: drain = column 0 (TU), source = column 1 (TERM_VCM)
        for col in w.cols: sd_column(C, x + col, ys, w.hh)
        C.via(2, x + w.cols[1] - .14, Y_LEG + 2.1 if not nvt else max(Y_LEG + 2.1, ys - w.hh + .25), x + w.cols[1] + .14, Y_LEG + 12.9 if not nvt else min(Y_LEG + 12.9, ys + w.hh - .25))
        # gate: via1 on the contact, Metal2 down across the ring to its Metal3 line
        gx, gyc = w.gates[0]
        C.metal(1, x + gx - .19, ys + gyc - .19, x + gx + .19, ys + gyc + .19); C.via(1, x + gx - .13, ys + gyc - .13, x + gx + .13, ys + gyc + .13)
        C.metal(2, x + gx - .2, gy[g] - .2, x + gx + .2, ys + gyc + .2)
        C.metal(3, x + gx - .2, gy[g] - .2, x + gx + .2, gy[g] + .2); C.via(2, x + gx - .14, gy[g] - .14, x + gx + .14, gy[g] + .14)
        # resistor heads: A (top) -> PAD bus, B (bottom) -> Metal2 down to the drain column
        ya = yr + r.head_a; yb = yr + r.head_b
        for yh in (ya, yb):
            C.metal(1, x - .99, yh - .23, x + .99, yh + .23); C.metal(2, x - .9, yh - .23, x + .9, yh + .23); C.via(1, x - .8, yh - .13, x + .8, yh + .13)
        C.metal(3, x - .9, ya - .23, x + .9, ya + .23); C.via(2, x - .8, ya - .14, x + .8, ya + .14)
        C.metal(2, x + w.cols[0] - .5, ys + w.hh - .5, x + (max(w.cols[0] + .2, -.6) if nvt else w.cols[0] + .2), yb + .23)   # nvt: TU column at -1.16, reach the head (+-0.9)
        C.label(tu, x + w.cols[0] - .15, ys + w.hh + .5, 'metal2')
        if sec:     # p+ island under the TU riser (anode), via1 onto the riser; switch ring columns dropped (bottom-bar chain instead)
            xa1, xa2 = x - .55 - aw / 2, x - .55 + aw / 2
            C.rect('mvpdiode', xa1, ypa, xa2, ypa + al); C.rect('mvpdiodec', xa1 + .15, ypa + .15, xa2 - .15, ypa + al - .15)
            C.metal(1, xa1 + .09, ypa + .09, xa2 - .09, ypa + al - .09)
            C.via(1, x - .68, ypa + al / 2 - .13, x - .42, ypa + al / 2 + .13)
            sch.append((f'DS_{name}_{k}', tu, f'DVDDS_{name}', 'DIODE', 'diode_pd2nw_06v0', round(aw * al, 4), round(2 * (aw + al), 4)))
            xs_.append(x); kx.append((k, q(x)))
            continue
        if nvt:     # no switch ring: Metal1 columns on the unit boundaries from the tap strip up to the resistor ring bottom bar
            for rx in (-(pitch / 2), pitch / 2):
                C.metal(1, x + rx - .115, Y_LEG - 1.025, x + rx + .115, yr + r.ring_bot + .3)
            continue
        # guard rings: switch ring columns up to the resistor ring bottom bar
        for rx in (-w.ring_x, w.ring_x):
            C.metal(1, x + rx - .115, ys + w.ring_ctop - .3, x + rx + .115, yr + r.ring_bot + (.295 if sw6 else .3))   # sw6: end inside the bar (0.22 um to the bar's corner piece)
    xa, xb = sorted((x0 - s * 2., x0 + s * ((len(gates) - 1) * pitch + 3.)))
    C.metal(1, xa + .2, ytop - .415, xb - .2, ytop - .185)                 # ring-top tie along the leg (bridges the group gap)
    out = dict(x=(xa, xb), gy=gy, ya=ya, ytop=ytop, vcm=(Y_LEG + 2., Y_LEG + 13.))
    if nvt:     # pwell over the switch row and the tap strip; the p-tap strip (contacts + Metal1) along the leg
        hs = max(sb.pw[3] - sb.pw[1], st.pw[3] - st.pw[1])
        C.rect('pwell', xa, Y_LEG - 1.4, xb, Y_LEG + hs)
        C.rect('mvpsubdiff', xa + .3, Y_LEG - 1.1, xb - .3, Y_LEG - .6); C.rect('mvpsubdiffcont', xa + .8, Y_LEG - .965, xb - .8, Y_LEG - .735)
        C.metal(1, xa + .3, Y_LEG - 1.025, xb - .3, Y_LEG - .675)
    if sec:
        xs_ = sorted(xs_); u1, u2 = xs_[0], xs_[-1]
        C.rect('nwell', u1 - 2.0, yn, u2 + 2.0, yn + hn)                    # cathode well strip + n+ tap strip + Metal1 (ends 1.6 um past the
        C.rect('mvnsubdiff', u1 - 1.6, yt, u2 + 1.6, yt + .5); C.rect('mvnsubdiffcont', u1 - 1.1, yt + .135, u2 + 1.1, yt + .365)   # end islands: NP.1)
        C.metal(1, u1 - 1.6, yt + .075, u2 + 1.6, yt + .425)
        yb3 = q(yn + .2); yt3 = q(yn + hn - .2)                               # DVDDS bus Metal3 + Metal4 over the row
        C.metal(3, u1 - 1.6, yb3, u2 + 1.6, yt3); C.metal(4, u1 - 1.6, yb3, u2 + 1.6, yt3); C.via(3, u1 - 1.3, yb3 + .3, u2 + 1.3, yt3 - .3)
        chans = [(q(a + .88), q(b - 1.18)) for a, b in zip(xs_[:-1], xs_[1:])]
        for c1, c2 in chans:                                                  # tap Metal1 -> via1 -> Metal2 stub -> via2 -> bus
            C.metal(2, c1, yb3, c2, yt3); C.via(1, c1 + .1, yt + .12, c2 - .1, yt + .38); C.via(2, c1 + .1, yb3 + .1, c2 - .1, yt3 - .1)
        # switch rings: Metal1 jumpers between neighbouring bottom bars, and from the innermost unit to the axis
        yb_ = (Y_LEG + .185, Y_LEG + .415)
        for a, b in zip(xs_[:-1], xs_[1:]): C.metal(1, a + 1.0, yb_[0], b - 1.0, yb_[1])
        if s < 0: C.metal(1, xs_[-1] + 1.0, yb_[0], AXIS, yb_[1])
        else: C.metal(1, AXIS, yb_[0], xs_[0] - 1.0, yb_[1])
        out.update(sec=dict(units=xs_, unit_x=dict(kx), chans=chans, row=(yn, yn + hn), bus=(yb3, yt3), tap=(yt, yt + .5)))
    return out


NAT_ENC, NAT_SPACE, NAT_COMP = 2.0, .74, .3     # NAT.1 overlap of COMP, NAT.7 NAT-NAT space, NAT.2 space to unrelated COMP


def leg_nat(C, P, x0, s, name, sch, nvt):
    """--nvt merged: termination leg with one native device per trim bit (gate group), each in its own NAT region (written to the GDS
    by nat_post()). Units k keep the resistor positions of leg(); the resistors of a group share one TU node TU_<leg>_<grp>
    (grp B = base, T0..T3 = trim bits): device TU columns and resistor heads B meet on a Metal3 track per group above the devices
    (two tracks, groups alternate). Device columns alternate VCM (even, both ends) / TU (odd)."""
    rb, rt = P['rb'], P['rt']
    pitch = q(2 * rb.ring_hw - .36)
    gates = ['TERM_ENABLE_LOCAL'] * N_BASE + TRIM_GATES
    gy = {g: q(Y_GATE0 + .8 * i) for i, g in enumerate(['TERM_ENABLE_LOCAL'] + [f'TERM_TRIM{k}' for k in range(4)])}
    groups = [('B', 'TERM_ENABLE_LOCAL', 'nvB')] + [(f'T{k}', f'TERM_TRIM{k}', f'nvT{k}') for k in range(4)]
    uk = [k * pitch + (0. if g == 'TERM_ENABLE_LOCAL' else 1.) for k, g in enumerate(gates)]
    yc0 = Y_LEG - .7 + NAT_COMP + NAT_ENC + .02        # COMP bottom: tap strip top (Y_LEG - .7) + 0.3 (NAT.2) + NAT 2.0 below COMP
    hmax = max(P[g[2]].dbox[3] - P[g[2]].dbox[1] for g in groups)
    nat_top = yc0 + hmax + NAT_ENC
    em = bool(nvt.get('em'))    # a13 (review-a12 F1): wide TU straps, multi-cut via2, 2.0 um tracks, 0.8 um resistor drops
    em2 = nvt.get('em') == 2    # a14 (review-a13 C1, design basis 15.75 mA static in one leg, codes 0..15): 1.9 um TU columns, 3.0 um tracks,
                                # 1.0 um drops, 1.0 um head landing bars
    trk = [(q(yc0 + hmax + .4), q(yc0 + hmax + 3.4)), (q(yc0 + hmax + 3.8), q(yc0 + hmax + 6.8))] if em2 else \
          [(q(yc0 + hmax + .4), q(yc0 + hmax + 2.4)), (q(yc0 + hmax + 2.8), q(yc0 + hmax + 4.8))] if em else \
          [(q(yc0 + hmax + .4), q(yc0 + hmax + .9)), (q(yc0 + hmax + 1.3), q(yc0 + hmax + 1.8))]
    ytop = q(max(nat_top + NAT_COMP, trk[1][1] + .3) - rb.ring_bot + rb.pw[3] + .05)
    cur = -rb.ring_hw; nats = []; devs = []
    for gi, (gn, gate, pn) in enumerate(groups):
        d = P[pn]; wc = d.dbox[2] - d.dbox[0]
        if gn == 'T0' and nvt.get('t0_shift'): cur += float(nvt['t0_shift'])     # a15: room for the outermost base unit's drop (EM basis B)
        uc = cur + NAT_ENC + wc / 2; cur = uc + wc / 2 + NAT_ENC + NAT_SPACE
        xc = q(x0 + s * uc); ys = q(yc0 - d.dbox[1]); devs.append((gn, gate, d, xc, ys))
        nats.append([xc + d.dbox[0] - NAT_ENC, yc0 - NAT_ENC, xc + d.dbox[2] + NAT_ENC, yc0 + (d.dbox[3] - d.dbox[1]) + NAT_ENC])
    assert cur - NAT_SPACE <= uk[-1] + rb.ring_hw + 2.5, (cur, uk[-1])
    ya = None; tu_x = {}; m3drops = []
    tucols = [xc + col for gn, gate, d, xc, ys in devs for i, col in enumerate(d.cols) if i % 2]
    tutop = [(xc + col, (trk[0] if gn in ('B', 'T1', 'T3') else trk[1])[1]) for gn, gate, d, xc, ys in devs for i, col in enumerate(d.cols) if i % 2]
    tuhw = .95 if em2 else .6
    hwg = lambda g: ((float(nvt.get('b_col_hw', .95)) if g == 'B' else float(nvt.get('t_col_hw', .95))) if em2 else .6)   # a15: base-device TU columns wider (EM basis B, code 0)
    tug = [(xc + col, (trk[0] if gn in ('B', 'T1', 'T3') else trk[1])[1], gn) for gn, gate, d, xc, ys in devs for i, col in enumerate(d.cols) if i % 2]
    for gn, gate, d, xc, ys in devs:
        tu = f'TU_{name}_{gn}'; nf = len(d.cols) - 1
        C.inst(f'txp_nv{gn}', xc, ys, f'TERM_{name}_SW_{gn}')
        for f_ in range(nf): sch.append((f'TERM_{name}_SW_{gn}_{f_}', tu, gate, 'TERM_VCM_BUS' if (nvt.get('disc') or nvt.get('disc2')) else 'TERM_VCM', 'VSS', 'nfet_06v0_nvt', nvt['wb'] if gn == 'B' else nvt['wt'], nvt['l']))
        y1, y2 = trk[0] if gn in ('B', 'T1', 'T3') else trk[1]
        for i, col in enumerate(d.cols):
            sd_column(C, xc + col, ys, d.hh)
            if i % 2 == 0: C.via(2, xc + col - .14, max(Y_LEG + 2.1, ys - d.hh + .25), xc + col + .14, min(Y_LEG + 2. + float(nvt.get('bus_h', 11.)) - .1, ys + d.hh - .25))   # a16 bus_h: taller bus, more cuts
            else:
                if em2: h_ = hwg(gn); C.metal(2, xc + col - h_, ys - d.hh + .03, xc + col + h_, y2); C.via(2, xc + col - h_ + .15, y1 + .15, xc + col + h_ - .15, y2 - .15)
                elif em: C.metal(2, xc + col - .6, ys - d.hh + .03, xc + col + .6, y2); C.via(2, xc + col - .45, y1 + .15, xc + col + .45, y2 - .15)
                else: C.metal(2, xc + col - .2, ys + d.hh - .5, xc + col + .2, y2); C.via(2, xc + col - .14, y1 + .11, xc + col + .14, y2 - .11)
                tu_x.setdefault(gn, []).append(xc + col)
        gyc = d.gates[0][1]; xs_ = [xc + g_[0] for g_ in d.gates]
        for gx in xs_:
            C.metal(1, gx - .19, ys + gyc - .19, gx + .19, ys + gyc + .19); C.via(1, gx - .13, ys + gyc - .13, gx + .13, ys + gyc + .13)
        C.metal(2, min(xs_) - .2, ys + gyc - .2, max(xs_) + .2, ys + gyc + .2)
        gx = xs_[0]
        C.metal(2, gx - .2, gy[gate] - .2, gx + .2, ys + gyc + .2)
        C.metal(3, gx - .2, gy[gate] - .2, gx + .2, gy[gate] + .2); C.via(2, gx - .14, gy[gate] - .14, gx + .14, gy[gate] + .14)
    gname = {g: n for n, g, _ in groups}
    for k, g in enumerate(gates):
        base = g == 'TERM_ENABLE_LOCAL'; r = rb if base else rt; gn = gname[g]
        x = q(x0 + s * uk[k]); yr = q(ytop - r.pw[3])
        C.inst('txp_rb' if base else 'txp_rt', x, yr, f'TERM_{name}_R_{k}')
        sch.append((f'TERM_{name}_R_{k}', f'PAD_{name}', f'TU_{name}_{gn}', 'VSS', 'ppolyf_u', 2., nvt['lb'] if base else nvt['lt']))
        ya = yr + r.head_a; yb = yr + r.head_b
        for yh in (ya, yb):
            C.metal(1, x - .99, yh - .23, x + .99, yh + .23); C.metal(2, x - .9, yh - .23, x + .9, yh + .23); C.via(1, x - .8, yh - .13, x + .8, yh + .13)
        if em2:     # a14: head B Metal1 pad extended up over the poly body, 2 rows of via1 (code 0: 1/8 of 15.75 mA per unit)
            e3 = .55 if (base and nvt.get('head3')) else 0.      # a16 "head3": base units (longer poly) get a third via1 row
            C.metal(1, x - 1.35, yb - .23, x + 1.35, yb + .71 + e3); C.via(1, x - 1.15, yb - .13, x + 1.15, yb + .65 + e3); C.metal(2, x - 1.6, yb - .5, x + 1.6, yb + .71 + e3)
        C.metal(3, x - .9, ya - .23, x + .9, ya + .23); C.via(2, x - .8, ya - .14, x + .8, ya + .14)
        y1, y2 = trk[0] if gn in ('B', 'T1', 'T3') else trk[1]
        if em:
            if em2:     # a14: drop as wide as the other-net columns allow (<= 1.8 um); own-group columns close by are merged into it
                other = [t for t, top, g2 in tug if g2 != gn and top >= y1 - .3]
                othg = [(t, g2) for t, top, g2 in tug if g2 != gn and top >= y1 - .3]
                gap = lambda v: min([abs(v - t) - hwg(g2) for t, g2 in othg] + [9.])          # edge distance to the nearest other-net column
                xd = max((q(x + o / 10) for o in range(-11, 12)), key=lambda v: (min(gap(v), 1.2), -abs(v - x)))
                cl = gap(xd); hw = max(.3, min(.9, cl - .3, 1.6 - abs(xd - x)))   # inside its own head bar
                assert cl >= hw + .3, ('drop vs TU column', name, k, xd, cl)
                ownc = [t for t, top, g2 in tug if g2 == gn and top >= y1 - .3 and abs(t - xd) < hw + hwg(gn) + .3]
                xlo = min([xd - hw] + [t - hwg(gn) for t in ownc]); xhi = max([xd + hw] + [t + hwg(gn) for t in ownc])
                C.metal(2, x - 1.6, yb - .5, x + 1.6, yb + .5)                        # head landing bar 1.0 um
                C.metal(2, xlo, y1, xhi, y2); C.metal(2, xd - hw, y1, xd + hw, yb + .23)   # merged part only within the track
                if nvt.get('drop_m3') and (y1, y2) == trk[0]: m3drops.append((xd, hw, y2, yb))
                # via2 under the drop always (also when merged with an own column: the current then goes down here instead of turning sideways),
                # clipped to stay >= 0.3 um from the column's own via array (x t +- 0.8)
                va, vb = xd - hw + .1, xd + hw - .1
                for t in ownc:
                    if t >= xd: vb = min(vb, t - hwg(gn) + .15 - .3)
                    else: va = max(va, t + hwg(gn) - .15 + .3)
                if vb - va >= .3: C.via(2, va, y1 + .15, vb, y2 - .15)
            else:
                near = [t for t, top in tutop if top >= y1 - .3]          # only TU columns whose Metal2 reaches this drop's track
                xd = max((q(x + o / 10) for o in range(-12, 13)), key=lambda v: (min(min([abs(v - t) for t in near] + [9.]), 1.7), -abs(v - x)))
                cl = min([abs(xd - t) for t in near] + [9.]); hw = .4 if cl >= 1.3 else .3     # drop half width 0.4 (0.3 where a TU column is close)
                assert cl >= hw + .9, ('drop vs TU column', name, k, xd, cl)
                C.metal(2, x - 1.6, yb - .23, x + 1.6, yb + .23)
                C.metal(2, xd - hw, y1, xd + hw, yb + .23); C.via(2, xd - hw + .15, y1 + .15, xd + hw - .15, y2 - .15)
        else:
            xd = max((x + o for o in (0., -.5, .5, -.25, .25, -.7, .7)), key=lambda v: min(min([abs(v - t) for t in tucols] + [9.]), .8))   # drop clear of TU columns
            C.metal(2, xd - .2, y1, xd + .2, yb + .23); C.via(2, xd - .14, y1 + .11, xd + .14, y2 - .11)
        tu_x.setdefault(gn, []).append(xd)
        C.label(f'TU_{name}_{gn}', x, yb, 'metal2')
    spans = {}
    m3_done = []
    for gn, xs_ in tu_x.items():
        y1, y2 = trk[0] if gn in ('B', 'T1', 'T3') else trk[1]
        e_ = (max(hwg("B"), hwg("T0")) + .1) if em2 else .7 if em else .2
        a, b = min(xs_) - e_, max(xs_) + e_; C.metal(3, a, y1, b, y2); spans[gn] = (a, b, y1)
    for g1, g2 in zip(list(spans)[:-1], list(spans)[1:]):     # same-track groups are never adjacent: check the two-apart ones
        pass
    for (n1, (a1, b1, t1)), (n2, (a2, b2, t2)) in [(u, v) for i, u in enumerate(spans.items()) for v in list(spans.items())[i + 1:]]:
        assert t1 != t2 or b1 + .3 < a2 or b2 + .3 < a1, ('TU track overlap', n1, n2)
    up = [(a, b) for a, b, t in spans.values() if t == trk[1][0]]
    for xd, hw, yt2, yb_ in m3drops:     # a16 "drop_m3": Metal3 over lower-track drops (current at 100BASE-TX), not where it would cross an upper-track bar
        if any(xd + hw + .3 > a and xd - hw - .3 < b for a, b in up): continue
        C.metal(3, xd - hw, yt2 - .2, xd + hw, yb_ + .5); C.via(2, xd - hw + .15, yb_ - .35, xd + hw - .15, yb_ + .35)
        C.metal(4, xd - hw, yt2 - .2, xd + hw, yb_ + .5); C.via(3, xd - hw + .15, yt2 + .1, xd + hw - .15, yb_ + .3)   # and Metal4 (no other Metal4 there)
    xa, xb = sorted((x0 - s * 2.2, x0 + s * max(uk[-1] + 3., cur)))
    C.metal(1, xa + .2, ytop - .415, xb - .2, ytop - .185)                 # ring-top tie along the leg
    yr0 = ytop - rb.pw[3]
    C.rect('pwell', xa, Y_LEG - 1.6, xb, yr0 + rb.pw[1] + .1)
    C.rect('mvpsubdiff', xa + .3, Y_LEG - 1.2, xb - .3, Y_LEG - .7); C.rect('mvpsubdiffcont', xa + .8, Y_LEG - 1.065, xb - .8, Y_LEG - .835)
    C.metal(1, xa + .3, Y_LEG - 1.125, xb - .3, Y_LEG - .775)
    if em:      # a13: a second p-tap strip just above the NAT row (the taller tracks moved the resistor rings up: latch-up 15 um)
        yt0 = q(nat_top + NAT_COMP); C.rect('mvpsubdiff', xa + .3, yt0, xb - .3, yt0 + .5); C.rect('mvpsubdiffcont', xa + .8, yt0 + .135, xb - .8, yt0 + .365)
        C.metal(1, xa + .3, yt0 + .075, xb - .3, yt0 + .425)
    for n1, n2 in zip(nats[:-1], nats[1:]):                                # tap strip -> resistor ring bars in the NAT gaps (and both ends)
        xm = (n1[2] + n2[0]) / 2 if s > 0 else (n1[0] + n2[2]) / 2
        xm = min((x0 + s * (u + o) for u in uk for o in (-pitch / 2, pitch / 2)), key=lambda v: abs(v - xm))   # on a resistor ring column
        C.metal(1, xm - .115, Y_LEG - 1.125, xm + .115, yr0 + rb.ring_bot + .3)
    for xm in (xa + .5, xb - .5): C.metal(1, xm - .115, Y_LEG - 1.125, xm + .115, yr0 + rb.ring_bot + .3)
    return dict(x=(xa, xb), gy=gy, ya=ya, ytop=ytop, vcm=(Y_LEG + 2., Y_LEG + 2. + float(nvt.get('bus_h', 11.))), nat=[[q(v) for v in n] for n in nats], tracks=trk)


def disconnect(C, d, sch, tx, down, g):
    """--nvt "disc": nfet_03v3 (w per finger, l, nf) between TERM_VCM_BUS (the native sources' Metal3/4 bus, x >= 20) and the TERM_VCM pin
    (the control cell's Metal4 trunk, x 4.8, with TERM_DISCHARGE inside the control cell = pin side). Gate TERM_ENABLE_LOCAL from its Metal3 line
    (y 353.4) under the device. Even columns (both ends) bus side -> Metal3 bar y 374.5-375.3 -> drop onto the bus at x 20.2-21; odd columns pin
    side -> Metal3 bar y 377-377.8 -> via3 onto the trunk."""
    xc = 13.; ys = q(354.4 - d.pw[1]); nf = len(d.cols) - 1
    assert xc + d.pw[0] >= 6.3 and xc + d.pw[2] <= 19.6 and ys + d.pw[3] <= 374., (d.pw, ys)
    C.inst('txp_dis', xc, ys, 'TERM_DISC')
    for f_ in range(nf): sch.append((f'TERM_DISC_{f_}', 'TERM_VCM_BUS', 'TERM_ENABLE_LOCAL', 'TERM_VCM', 'VSS', 'nfet_03v3', d.w_f, d.l_))
    b1, b2 = (374.5, 375.3), (377., 377.8)
    for i, col in enumerate(d.cols):
        x = xc + col; sd_column(C, x, ys, d.hh); y1, y2 = b1 if i % 2 == 0 else b2
        C.metal(2, x - .2, ys + d.hh - .5, x + .2, y2); C.via(2, x - .14, y1 + .12, x + .14, y2 - .12)
    xs = [xc + c_ for c_ in d.cols]
    C.metal(3, min(xs) - .2, b1[0], 21., b1[1]); C.metal(3, 20.2, 370.5, 21., b1[1])          # bus-side bar + drop onto the bus (Metal3 360-371 from x 20)
    C.metal(3, tx['TERM_VCM'] - .3, b2[0], max(xs) + .2, b2[1])                              # pin-side bar to the trunk
    down('TERM_VCM', b2[0]); C.via(3, tx['TERM_VCM'] - .14, b2[0] + .12, tx['TERM_VCM'] + .14, b2[1] - .12)
    C.label('TERM_VCM_BUS', 20.6, 373., 'metal3')
    gyc = d.gates[0][1]; gxs = [xc + g_[0] for g_ in d.gates]; ye = g['gy']['TERM_ENABLE_LOCAL']
    for gx in gxs: C.metal(1, gx - .19, ys + gyc - .19, gx + .19, ys + gyc + .19); C.via(1, gx - .13, ys + gyc - .13, gx + .13, ys + gyc + .13)
    C.metal(2, min(gxs) - .2, ys + gyc - .2, max(gxs) + .2, ys + gyc + .2)
    C.metal(2, gxs[0] - .2, ye - .2, gxs[0] + .2, ys + gyc + .2); C.via(2, gxs[0] - .14, ye - .14, gxs[0] + .14, ye + .14)
    return dict(xc=xc, ys=ys, pw=d.pw, cols=xs)


def disconnect2(C, d, sch, tx, down, g, rows=1):
    """--nvt "disc2": [w, l, nf, rows] (a11): wide nfet_03v3 disconnect, common-mode path <= 5 ohm (review-a10 F1: the whole tail current returns
    through TERM_VCM), in the free area west of the driver (x 10-82, y 416-620). `rows` identical devices stacked in y (finger height kept short
    for the 15 um latch-up tap distance), gate contacts on top. Per row: even columns (bus side) down to a Metal3 bar under the row (row 0 also
    Metal4), odd columns (pin side) up to a Metal4+5 bar over the row. Bus bars join a Metal2(+3) riser at x 10.5-20.5 down to the TERM_VCM_BUS
    bus (extended west to x 10.5; Metal3 broken at the PAD_N Metal3 line and at the gate lines). Pin bars join two 24 um Metal4+5 strips
    (MSLOT.1: <= 30 um) up to the top edge (Metal4 only across the VSS Metal5 jog at y 623-624.4, Metal5 only over the control cell), Metal4 pin
    pad (TERM_VCM). The control cell's TERM_VCM trunk (TERM_DISCHARGE) joins the pin on Metal5 at the top. Gate per row: Metal1 bar on the
    contacts, Metal2 stub at column 0, Metal3 line west to the TERM_ENABLE_LOCAL trunk (via3)."""
    xs0, xs1 = (9.6, 21.9) if RISER_WIDE else (10.5, 20.5)   # 9.6: clear of the PAD_N trunk's Metal3 landing at x 8.6-9.0    # a12: riser widened (EM: Metal2 alone across the Metal3 breaks)
    nf = len(d.cols) - 1; xc = q(24.5 - d.pw[0]); assert xc + d.pw[2] <= 81., (xc, d.pw)
    xs = [xc + c_ for c_ in d.cols]; te = tx['TERM_ENABLE_LOCAL']
    ypn = g['ya'] - .23 + 20. + 6.                           # PAD_N Metal3 jog from its control-cell trunk (y ypn +- 0.2; a12: 415.24)
    pwb = max(427., q(ypn + .2 + .5 + 9.8)); breaks = [(ypn - .55, ypn + .55)]; yb_top = None; rows_info = []
    for r in range(rows):
        ys = q(pwb - d.pw[1]); yb0, yb1 = pwb - 9.8, pwb - .8
        C.inst('txp_dis', xc, ys, f'TERM_DISC_{r}')
        for f_ in range(nf): sch.append((f'TERM_DISC_{r}_{f_}', 'TERM_VCM_BUS', 'TERM_ENABLE_LOCAL', 'TERM_VCM', 'VSS', 'nfet_03v3', d.w_f, d.l_))
        gyc = ys + d.gates[0][1]; ytr = ys + d.pw[3]; yp0, yp1 = q(ytr + 1.0), q(ytr + 7.0)
        for i, x in enumerate(xs):
            sd_column(C, x, ys, d.hh)
            if i % 2 == 0:
                C.metal(2, x - .2, yb0 + .2, x + .2, ys - d.hh + .5); C.via(2, x - .14, yb0 + .4, x + .14, yb1 - .2)
                if DISC_M3:     # a16: Metal3 strip over the bus-side column (doubles its conductance; joins the bus bar below); edge columns widened outward
                    xl_ = x - (1.0 if i == 0 else .2); xr_ = x + (1.0 if i == len(xs) - 1 else .2)
                    C.metal(3, xl_, yb0 + .2, xr_, ys + d.hh - .1); C.via(2, x - .14, ys - d.hh + .3, x + .14, ys + d.hh - .3)
            else:
                C.metal(2, x - .2, ys + d.hh - .5, x + .2, yp0 + (3.0 if DISC_M3 else 1.4)); C.metal(3, x - .2, yp0 + .2, x + .2, yp0 + (3.0 if DISC_M3 else 1.4))
                if DISC_M3: C.via(2, x - .14, yp0 + .25, x + .14, yp0 + 1.35); C.via(3, x - .14, yp0 + 1.7, x + .14, yp0 + 2.85)   # a16: 2 + 2 cuts
                else: C.via(2, x - .14, yp0 + .3, x + .14, yp0 + .62); C.via(3, x - .14, yp0 + .95, x + .14, yp0 + 1.27)
        if r == 0: C.stack(3, 4, xs0, yb0, max(xs) + .4, yb1, enc=.3)
        else: C.metal(3, xs0, yb0, max(xs) + .4, yb1)
        C.stack(4, 5, min(xs) - .4, yp0, max(xs) + .4, yp1, enc=.3)
        C.metal(1, min(xs) - .3, gyc - .19, max(xs) + .1, gyc + .19)
        x0 = xs[0]; C.via(1, x0 - .13, gyc - .13, x0 + .13, gyc + .13); C.metal(2, x0 - .2, gyc - .2, x0 + .2, gyc + 1.6)
        C.metal(3, te - .3, gyc + .9, x0 + .3, gyc + 1.6); C.via(2, x0 - .14, gyc + 1.1, x0 + .14, gyc + 1.4)
        C.metal(4, te - .2, gyc + .9, te + .2, gyc + 1.6); C.via(3, te - .14, gyc + 1.11, te + .14, gyc + 1.39)
        breaks.append((gyc + .6, gyc + 1.9)); yb_top = yb1; rows_info.append(dict(ys=ys, bus_bar=[yb0, yb1], pin_bar=[yp0, yp1], gate_y=gyc))
        if r == 0: ystrap = yp1 - 1.
        pwb = q(yp1 + 10.5)
    # riser: Metal2 continuous, Metal3 in segments between the breaks
    C.metal(2, xs0, 370.5, xs1, yb_top)
    a_ = 370.5
    for b0, b1 in sorted(x for x in breaks if x[1] < yb_top) + [(yb_top, yb_top)]:
        if b0 - a_ > 1.:
            C.metal(3, xs0, a_, xs1, b0)
            if b0 - a_ > 1.6: C.via(2, xs0 + .3, a_ + .4, xs1 - .3, b0 - .4)
        a_ = b1
    if RISER_WIDE:      # a12: Metal4 over the riser too (broken only at the PAD_P Metal4 line y 403.6-404.4): >= 2 layers at every height
        yp4 = g['ya'] - .23 + 9.6                                # PAD_P Metal4 jog from its control-cell trunk (y yp4 .. yp4 + 0.8)
        segs4 = ((370.5, yp4 - .4), (yp4 + 1.2, yb_top))
        for a4, b4 in segs4: C.metal(4, xs0, a4, xs1, b4)
        a_ = 370.5
        for b0, b1 in sorted(x for x in breaks if x[1] < yb_top) + [(yb_top, yb_top)]:     # via3 only where Metal3 and Metal4 overlap
            for a4, b4 in segs4:
                lo, hi = max(a_, a4, 370.9) + .4, min(b0, b4) - .4
                if hi - lo > .6: C.via(3, xs0 + .3, lo, xs1 - .3, hi)
            a_ = b1
    vb1 = g['vcm'][1]
    C.metal(3, xs0, 360., 20.5, vb1); C.metal(4, xs0, 360., 20.5, vb1); C.via(3, xs0 + .3, 360.3, 19.7, 370.7)
    C.label('TERM_VCM_BUS', (xs0 + xs1) / 2, 395., 'metal3')
    sx0, sx1 = 25., 75.
    for a2, b2 in ((sx0, (sx0 + sx1) / 2 - 1.), ((sx0 + sx1) / 2 + 1., sx1)):
        C.stack(4, 5, a2, ystrap, b2, 622.4, enc=.3)
        C.metal(4, a2, 622., b2, 626.5); C.stack(4, 5, a2, 625., b2, 626.5, enc=.3)
        C.metal(5, a2, 625., b2, Y_TOP)
    C.stack(4, 5, sx0, Y_TOP - 1.7, sx1, Y_TOP, enc=.3); C.label('TERM_VCM', (sx0 + sx1) / 2, Y_TOP - .5, 'metal4', True)
    t = tx['TERM_VCM']
    C.stack(4, 5, t - .4, Y_TOP - 2.7, t + .4, Y_TOP - .9, enc=.2); C.metal(5, t - .4, Y_TOP - 2.7, sx0 + 1., Y_TOP - .9)
    return dict(xc=xc, pw=d.pw, cols=[xs[0], xs[-1]], rows=rows_info)


def nat_post(work, top, boxes, top_ext=0.):
    """--nvt merged: NAT (5/0) per native device, COMP + 2.0 um (the installed Magic export writes no NAT), and DUALGATE (55/0) over it (NAT.8):
    one DUALGATE box per leg over the bbox of its NATs (per-NAT boxes 0.74 um apart violate DV.2)."""
    half = lambda f: [b for b in boxes if f((b[0] + b[2]) / 2)]
    dg = [[min(b[0] for b in g), min(b[1] for b in g) - .5, max(b[2] for b in g), max(b[3] for b in g) + top_ext] for g in (half(lambda x: x < AXIS), half(lambda x: x > AXIS)) if g]
    (work / 'nat.py').write_text('import klayout.db as k\n' f'l = k.Layout(); l.read("/work/{top}.gds"); c = l.cell("{top}")\n'
                                 f'for b in {boxes!r}:\n    c.shapes(l.layer(5, 0)).insert(k.DBox(*b))\n'
                                 f'for b in {dg!r}:\n    c.shapes(l.layer(55, 0)).insert(k.DBox(*b))\n'
                                 'r = k.Region(c.shapes(l.layer(55, 0))); r.merge(); c.shapes(l.layer(55, 0)).clear(); c.shapes(l.layer(55, 0)).insert(r)\n'
                                 f'l.write("/work/{top}.gds")\n')
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{work}:/work',
                    IMAGE, '/work/nat.py'], check=True, timeout=600)
    return dict(nat_boxes=boxes)


def site(C, ox, name, W, upx=(), yu=107.):
    """Primary diodes in the pad site (pad_tlp_flat pattern, Y moved under the DVDD / inner DVSS bands) + bond pad + neck."""
    Y = 146.
    def via1(x, y): C.metal(1, x - .19, y - .19, x + .19, y + .19); C.via(1, x - .13, y - .13, x + .13, y + .13); C.metal(2, x - .2, y - .2, x + .2, y + .2)
    C.c += [f'getcell Bondpad_5LM child 0 0 parent {q(ox + 5.5)} 0', f'identify BOND_{name}']
    nd = [(10 + 6 * i, 'nd') for i in range(4)]; pw = [(48 + 6 * i, 'pw') for i in range(4)]
    for k, (x, t) in enumerate(nd + pw):
        C.c += [f'getcell {"diode_nd2ps_06v0" if t == "nd" else "diode_pd2nw_06v0"} child 0 0 parent {q(ox + x)} {Y}', f'identify D{name}{k}']
        for dy in range(1, 12): via1(ox + x, Y + dy)
        if t == 'nd':
            for dy in range(1, 12): via1(ox + x + 1.03, Y - dy)
        else:
            for dy in range(6, 12): via1(ox + x + .99, Y - dy)
            for dy in range(1, 6): via1(ox + x + 1.87, Y - dy)
    m2 = lambda *a: C.metal(2, ox + a[0], a[1], ox + a[2], a[3])
    m2(8, Y + .5, 69, Y + 11.5)                                         # PAD bar
    m2(9, Y - 20, 30, Y - .5); m2(45, Y - 5.5, 69, Y - .5)               # DVSS bars
    m2(45, Y - 20, 45.7, Y - .5); m2(45, Y - 20, 47.5, Y - 15)
    C.metal(1, ox + 27.9, Y - 19.4, ox + 47.3, Y - 15.6)
    for xx in (28.5, 29.2, 46.2, 46.9):
        for dy in (16, 17, 18, 19): via1(ox + xx, Y - dy)
    m2(46.2, Y - 11.5, 73. if UP2 else 69, Y - 6.)                      # DVDD bar
    if UP2:
        # second up-diode row right of the neck (pd2nw only): PAD bar from the neck, DVDD bar under the ring DVDD band 166-181,
        # joined to the first DVDD bar on Metal2 (x 72-73); substrate rings back to the first tap bar on Metal1 (x 73.3-74)
        Y2 = Y + 32.
        for k, x in enumerate(UP2):
            C.c += [f'getcell diode_pd2nw_06v0 child 0 0 parent {q(ox + x)} {Y2}', f'identify D{name}U{k}']
            for dy in range(1, 12): via1(ox + x, Y2 + dy)
            for dy in range(6, 12): via1(ox + x + .99, Y2 - dy)
            for dy in range(1, 6): via1(ox + x + 1.87, Y2 - dy)
        m2(52., Y2 + .5, UP2[-1] + 2.2, Y2 + 11.5)                       # PAD bar 2
        m2(UP2[0] - 1.8, Y2 - 11.5, 73., Y2 - 6.)                        # DVDD bar 2
        m2(72., Y - 11.5, 73., Y2 - 6.)                                  # DVDD link
        m2(UP2[0] - 3., Y2 - 5.5, UP2[-1] + 2.9, Y2 - .5)                # tap bar 2
        for yy, xa in ((Y - 3.4, 68.65), (Y2 - 3.4, UP2[-1] + 2.65)):    # tap bars -> Metal1 link
            C.metal(1, ox + xa - .25, yy - .6, ox + 74., yy + .6)
            C.via(1, ox + xa - .13, yy - .39, ox + xa + .13, yy + .39); C.metal(2, ox + xa - .2, yy - .5, ox + xa + .2, yy + .5)
        C.metal(1, ox + 73.3, Y - 4., ox + 74., Y2 - 2.8)
        C.stack(2, 3, ox + UP2[0] - 1.3, Y2 - 11.3, ox + UP2[-1] + 2., Y2 - 6.2, enc=.3)   # second landing, ring DVDD band 166-181
    if upx:
        # --sw6 extra up-diode row right of the neck between the bond pad and the first row (the y-mirror of the first row's pd2nw pattern):
        # PAD bar below (joined to the neck), substrate-tap bar (landing on the ring DVSS band 70-117), DVDD bar up to a landing on the ring
        # DVDD band 118-125, linked on Metal2 (x 71-73) to the first row's DVDD bar.
        for k, x in enumerate(upx):
            C.c += [f'getcell diode_pd2nw_06v0 child 0 0 parent {q(ox + x)} {yu}', f'identify D{name}V{k}']
            for dy in range(1, 12): via1(ox + x, yu - dy)
            for dy in range(6, 12): via1(ox + x + .99, yu + dy)
            for dy in range(1, 6): via1(ox + x + 1.87, yu + dy)
        xa, xb = min(upx) - 2., max(upx) + 2.2
        assert xa >= 53.5 and xb <= 73., (xa, xb)
        m2(52.5, yu - 11.5, xb, yu - .5)                                  # PAD bar from the neck
        m2(xa, yu + .5, xb, yu + 5.5)                                     # substrate-tap bar
        C.stack(2, 3, ox + xa + .3, yu + .8, ox + xb - .3, min(yu + 5.2, 116.5), enc=.3)
        m2(xa, yu + 6., xb, 125.); m2(71., 124., 73., 134.6)               # DVDD bar + link to the first row's DVDD bar
        C.stack(2, 3, ox + xa + .3, 118.5, ox + xb - .3, 124.5, enc=.3)
    m2(31.5, Y - 21.5, 44.5, Y + 1.)                                    # riser through the gap between the bars
    m2(23., 55, 53., Y - 21.)                                           # 30 um from the bond pad
    # ring landings on Metal3 (the ring's own Metal3 is there at assembly): DVSS band 126-133, DVDD band 134-149
    C.stack(2, 3, ox + 9.5, 126.4, ox + 29.5, 132.6, enc=.3); C.label('VSS', ox + 20, 129.5, 'metal3', True)
    C.stack(2, 3, ox + 46.7, 134.7, ox + 68.5, 139.8, enc=.3); C.label(f'DVDD_{name}', ox + 57, 137.2, 'metal3', True)
    C.metal(2, ox + 37.5 - W / 2, Y + .5, ox + 37.5 + W / 2, Y + 30.)   # neck start (continued by the caller)
    return Y + 11.5


def merge_markers(work, top):
    """Implant / marker gaps of the PCells below the KLayout spacing rules (PP.2 etc.): marker_merge.py on the final GDS."""
    (work / 'mm.py').write_text('import sys, json\nsys.path.insert(0, "/tool")\nimport klayout.db as k, marker_merge\n'
                                f'l = k.Layout(); l.read("/work/{top}.gds"); c = l.cell("{top}")\n'
                                f'r = marker_merge.merge(l, c); l.write("/work/{top}.gds"); json.dump(r, open("/work/marker-merge.json", "w"), indent=1)\n')
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{work}:/work',
                    '-v', f'{HERE}:/tool:ro', IMAGE, '/work/mm.py'], check=True, timeout=600)
    return json.loads((work / 'marker-merge.json').read_text())


def make_ctl(work, term_buf_p=4., disch_l=2.):
    """Control cell pt_tx_ctl (convkit rows, as pt_hs_leg): TERM / DETECT enable buffers on VDD with their bleed chains,
    detect sources and isolators, TERM_VCM discharge resistor. Devices and sizes as circuits.wired_transmit."""
    import hs_leg_layout as hl
    ck = hl.ck
    d = []
    for c in ('DETECT', 'TERM'):
        for suf, i, o in (('INV', c + '_ENABLE', c + '_ENABLE_B'), ('BUF', c + '_ENABLE_B', c + '_ENABLE_LOCAL')):
            d.append(ck.Mos(f'{c}_{suf}_N', 'nfet_06v0', 2., .7, o, i, 'VSS', 'VSS'))
            d.append(ck.Mos(f'{c}_{suf}_P', 'pfet_06v0', term_buf_p if (c, suf) == ('TERM', 'BUF') else 4., .55, o, i, 'VDD', 'VDD'))
        prev = c + '_ENABLE_LOCAL'
        for k in range(8):
            nxt = 'VSS' if k == 7 else f'{c}_BLEED_{k}'
            d.append(ck.Res(f'{c}_BLEED_{k}', 1., 12.5, prev, nxt, 'VSS')); prev = nxt
    for leg in ('P', 'N'):
        d.append(ck.Mos(f'DETECT_{leg}_SOURCE', 'pfet_03v3', 4., 2., f'DETECT_{leg}_I', 'DETECT_PBIAS', 'VDD', 'VDD'))
        d.append(ck.Mos(f'DETECT_{leg}_ISOLATE', 'nfet_06v0', 4., .7, f'DETECT_{leg}_I', 'DETECT_ENABLE_LOCAL', f'PAD_{leg}', 'VSS'))
    d.append(ck.Res('TERM_DISCHARGE', 2., disch_l, 'TERM_VCM', 'VSS', 'VSS'))   # a12 "disch": longer (EM: 1.2-1.7 mA DC through single cuts at l 2)
    names = lambda f: [x.name for x in d if f(x)]
    rows = [names(lambda x: isinstance(x, ck.Mos) and x.model == 'nfet_06v0'), names(lambda x: isinstance(x, ck.Mos) and x.model.startswith('pfet')),
            names(lambda x: isinstance(x, ck.Res))]
    ports = ['VDD', 'VSS', 'TERM_ENABLE', 'TERM_ENABLE_LOCAL', 'DETECT_ENABLE', 'DETECT_PBIAS', 'PAD_P', 'PAD_N', 'TERM_VCM']
    c = ck.Circuit('pt_tx_ctl', ports, d, rows=rows, wide_nets={'VSS': 1.0, 'VDD': 1.0})
    w = work / 'ctl'; w.mkdir()
    sch = c.spice(include_macros=False); (w / 'pt_tx_ctl.sch.spice').write_text(sch)
    L = ck.Layout(c, w).build(); L.write()
    (w / 'pt_tx_ctl.lvs_sch.spice').write_text(L.lvs_reference(sch))
    res = ck.lvs(w, 'pt_tx_ctl.lvs.spice', 'pt_tx_ctl', 'pt_tx_ctl.lvs_sch.spice', 'pt_tx_ctl')
    trunks = {}
    for s in L.shapes:
        if s[0] == 'metal4' and s[5] in ports and s[4] - s[2] > 3 * (s[3] - s[1]) and abs((s[1] + s[3]) / 2 - L.trunk_x.get(s[5], 1e9)) < .01:
            trunks[s[5]] = [s[1], s[2], s[3], s[4]]
    info = dict(bbox=L.bbox, trunk_x=L.trunk_x, trunks=trunks, drc=L.report.get('drc_count'), lvs=res['final'], lvs_unique=res['match_unique'],
                antenna_diodes=L.antenna_diodes)
    (w / 'ctl-info.json').write_text(json.dumps(info, indent=1, default=str) + '\n')
    return info


def generate(work, part='all', scales=None, sec=None, sw6=None, upx=None, nvt=None, top_pins=False):
    work.mkdir(parents=True, exist_ok=False)
    global Y_DRV0, CTL_Y, Y_TOP, TOP_PINS, DISC, RISER_WIDE, DISC_M3
    DISC_M3 = bool(nvt and nvt.get('disc_m3'))
    RISER_WIDE = bool(nvt and nvt.get('riser_wide'))
    TOP_PINS = bool(top_pins); DISC = bool(nvt and nvt.get('merged') and (nvt.get('disc') or nvt.get('disc2')))
    assert not DISC or TOP_PINS, 'disc needs --top-pins (the pin moves to the control-cell trunk at the top edge)'
    if sw6 is not None: sw6 = dict(dict(w=66., lb=2.0, lt=1.0, upx=[], yu=107., bufp=40.), **sw6)
    scales = scales or {}
    widths = {b: round(20. * scales.get(b, 1.), 2) for b in ('MAIN', 'POST', 'TMDS')}
    if nvt is not None: nvt = dict(dict(wb=16., wt=19., l=1.8, lb=1.0, lt=1.0), **nvt)
    P, spec = make_prims(work, widths, sw6, nvt)
    global CTL_EARLY
    CTL_EARLY = None
    if nvt and nvt.get('disch') and part == 'all':      # a12: the longer TERM_DISCHARGE makes the control cell taller -> the top edge (pins) moves up
        CTL_EARLY = make_ctl(work, disch_l=float(nvt['disch']))
        Y_TOP = q(CTL_Y + CTL_EARLY['trunks']['VDD'][3])
    if sw6:     # extra leg height (switch row, resistor row) -> everything above the leg moves up by DY
        h = lambda a, b: max(P[a].pw[3] - P[a].pw[1], P[b].pw[3] - P[b].pw[1])
        dy = (h('tsb', 'tst') + h('rb', 'rt')) - ((P0_SW_H := 23.16) + (P0_R_H := 5.18))
        dy = __import__('math').ceil(dy * 2 - 1e-9) / 2
        Y_DRV0, CTL_Y = 432. + dy, 626. + dy; Y_TOP = CTL_Y + 66.26
        sw6['dy'] = dy
    for n in ('diode_nd2ps_06v0', 'diode_pd2nw_06v0'): shutil.copy(PRIM / f'{n}.gds', work / f'{n}.gds')
    top = 'pad_txpad'
    C = Cell(top); sch = []
    C.c += ['gds read diode_nd2ps_06v0.gds', 'gds read diode_pd2nw_06v0.gds', f'load {top}_h', 'units microns']
    info = dict(part=part, switch_widths_um=widths)
    if sw6: info['sw6'] = sw6
    if upx: info['upx'] = upx
    if nvt: info['nvt'] = nvt
    if part in ('drv', 'all'):
        d = driver(C, P, AXIS, Y_DRV0, sch, line_top=Y_TOP if part == 'all' else None); info['driver'] = d
        for net, xl in d['lines'].items():
            if TOP_PINS and part == 'all':     # ASM-2: via2 + Metal3 pin at the top end of every line
                for xx in xl: C.stack(2, 3, AXIS + xx - .2, Y_TOP - .9, AXIS + xx + .2, Y_TOP, enc=.06); C.label(net, AXIS + xx, Y_TOP - .4, 'metal3', True)
            else: C.label(net, AXIS + xl[0], d['ytop'] - .4, 'metal2', True)
        for s, n in ((1, 'P'), (-1, 'N')): C.label('PAD_' + n, AXIS + s * (d['bus']['pad'][0] + 2), Y_DRV0, 'metal5', part == 'drv')
        if not (TOP_PINS and part == 'all'): C.label('VSS', AXIS, Y_DRV0, 'metal5', True)
        # join the doubled gate lines above the driver on Metal3
        yj = d['ytop']
        for i, net in enumerate(n for n, xl in d['lines'].items() if len(xl) == 2):
            a, b = sorted(d['lines'][net]); y = yj - .5 - 1.2 * i - (13.2 - 11.0 + 1.5) * 0 + 0
            y = d['y'][1] + 1.0 + 1.0 * i
            for xx in (a, b): C.stack(2, 3, AXIS + xx - .2, y - .2, AXIS + xx + .2, y + .2, enc=.06)
            C.metal(3, AXIS + a - .2, y - .2, AXIS + b + .2, y + .2)
    if part in ('leg', 'all'):
        pitch = 2 * P['rb'].ring_hw - .36
        xin = 6.5 + 2.                                               # innermost unit centre: AXIS -/+ xin
        for s, n in ((-1, 'P'), (1, 'N')):
            g = leg(C, P, AXIS + s * xin, s, n, sch, sec, sw6, nvt); info['leg_' + n] = g
        gy = g['gy']; xl = info['leg_P']['x'][0]; xr = info['leg_N']['x'][1]
        full = part == 'all'
        for net, y in gy.items():
            C.metal(3, xl, y - .2, X_EAST if full and net != 'TERM_ENABLE_LOCAL' else xr, y + .2)
            if TOP_PINS and full and net != 'TERM_ENABLE_LOCAL': continue
            C.label(net, (X_EAST - 1) if full and net != 'TERM_ENABLE_LOCAL' else xl + 1, y, 'metal3', net != 'TERM_ENABLE_LOCAL' or not full)
        # TERM_VCM bus (Metal3 + Metal4) across both legs, out to the east cell edge
        v1, v2 = g['vcm']
        C.stack(3, 4, 20. if full else xl, v1, X_EAST if full else xr, v2, enc=.3)
        if not (TOP_PINS and full): C.label('TERM_VCM', (X_EAST - 2) if full else xl + 2, (v1 + v2) / 2, 'metal4', True)
        if part == 'leg':
            for s, n in ((-1, 'P'), (1, 'N')):
                a, b = info['leg_' + n]['x']; C.stack(3, 5, a, g['ya'] - .23, b, g['ya'] + 19.77, enc=.3); C.label('PAD_' + n, (a + b) / 2, g['ya'] + 5, 'metal5', True)
            a = info['leg_P']['x'][0]; C.metal(1, a, g['ytop'] - .4, xr, g['ytop'] - .1); C.label('VSS', a + 1, g['ytop'] - .25, 'metal1', True)
    if part == 'ctl':
        print(json.dumps(make_ctl(work), default=str)); return
    if part == 'all':
        g = info['leg_P']; d = info['driver']
        yb1 = g['ya'] - .23; yb2 = yb1 + 20.                         # horizontal PAD buses (Metal3-5)
        for s, n in ((-1, 'P'), (1, 'N')):
            bond = AXIS + s * 105.5
            ytop = site(C, bond - 37.5, n, NECK_W, **(dict(upx=sw6['upx'], yu=sw6['yu']) if sw6 and sw6.get('upx') else dict(upx=upx['x'], yu=upx.get('yu', 107.)) if upx else {}))
            C.metal(2, bond - NECK_W / 2, ytop, bond + NECK_W / 2, yb2)
            xi = AXIS + s * 7.4                                      # inner end of the bus (gap for the VSS column)
            a, b = sorted((bond + s * NECK_W / 2, xi)); a, b = min(a, bond - NECK_W / 2), max(b, bond + NECK_W / 2)
            C.stack(3, 5, a, yb1, b, yb2, enc=.3)
            C.via(2, bond - NECK_W / 2 + .3, yb1 + 1.2, bond + NECK_W / 2 - .3, yb2 - .3)
            if sw6:     # the neck grew by DY: Metal3-5 over it between the TERM_VCM bus (top 371) and the horizontal PAD bus
                C.stack(2, 5, bond - NECK_W / 2, 372., bond + NECK_W / 2, yb1 + 1., enc=.3)
            pa, pb = sorted((AXIS - s * d['bus']['pad'][0], AXIS - s * d['bus']['pad'][1]))   # driver PAD bus down onto it
            C.metal(4, pa, yb1, pb, d['y'][0]); C.metal(5, pa, yb1, pb, d['y'][0]); C.via(4, pa + .5, yb2 + .5, pb - .5, d['y'][0])
            C.label('PAD_' + n, bond, yb1 + 10, 'metal5', True)
        # VSS: driver bus down through the gap between the PAD buses to the ring DVSS band (depth 342-348.39)
        C.stack(4, 5, AXIS - 6.2, yb1 - 2., AXIS + 6.2, d['y'][0] + .5, enc=.3)
        C.metal(5, AXIS - 15, 342.5, AXIS + 15, yb1 - 1.5)
        C.stack(3, 5, AXIS - 15, 342.5, AXIS + 15, 348., enc=.3)
        # leg guard rings: tie the two legs' ring bars together at the axis and to the VSS column
        C.metal(1, info['leg_P']['x'][1] - 2.2, g['ytop'] - .42, info['leg_N']['x'][0] + 2.2, g['ytop'] - .12)
        C.stack(1, 4, AXIS - 1.5, g['ytop'] - 1.2, AXIS + 1.5, g['ytop'] - .1)
        if sec:
            # switch-ring chain (bottom bars) -> VSS column (Metal5) at the axis, between the gate lines and the TERM_VCM bus
            C.stack(1, 5, AXIS - 1.5, Y_LEG - .7, AXIS + 1.5, Y_LEG + 1.6, enc=.3)
            # DVDDS_<leg>: channels inside the site x range down to a Metal2 plate on the ring DVDD bands (rail tile: no Metal2)
            for n, (sx1, sx2) in (('P', (53.4, 74.6)), ('N', (211.4, 233.1))):
                sg = info['leg_' + n]['sec']; ch = [c for c in sg['chans'] if c[0] >= sx1 and c[1] <= sx2]
                assert len(ch) >= 4, (n, ch)
                for c1, c2 in ch: C.metal(2, c1, 352.7, c2, sg['bus'][1])
                C.metal(2, sx1, 205.5, sx2, 352.7)
                for b1, b2 in ((206., 213.), (214., 229.), (262., 269.), (270., 277.), (278., 285.), (294., 301.), (334., 341.)):   # ring sub-bands (1 um slots kept free)
                    C.stack(2, 3, sx1 + .3, b1 + .5, sx2 - .3, b2 - .5, enc=.3)
                C.label(f'DVDDS_{n}', (sx1 + sx2) / 2, 337.5, 'metal3', True)
                info['sec_' + n] = dict(site_x=[sx1, sx2], chans_down=ch, landing_bands=[[206, 213], [214, 229], [262, 269], [270, 277], [278, 285], [294, 301], [334, 341]])
        # control cell and its nets
        ctl = CTL_EARLY or make_ctl(work, **(dict(term_buf_p=sw6['bufp']) if sw6 else {})); info['ctl'] = ctl
        for f in (work / 'ctl').glob('*.mag'): shutil.copy(f, work / f.name)
        C.c += [f'getcell pt_tx_ctl child 0 0 parent {CTL_X} {CTL_Y}', 'identify XCTL']; C.ninst += 1
        tx = {n: q(CTL_X + x) for n, x in ctl['trunk_x'].items()}; tb = {n: CTL_Y + v[1] for n, v in ctl['trunks'].items()}
        down = lambda n, y: C.metal(4, tx[n] - .2, y, tx[n] + .2, tb[n] + .5)
        for n in ('VDD', 'TERM_ENABLE', 'DETECT_ENABLE', 'DETECT_PBIAS'): C.label(n, tx[n], Y_TOP - .5, 'metal4', True)
        if TOP_PINS:
            C.label('VSS', tx['VSS'], Y_TOP - .5, 'metal4', True)
            if nvt and nvt.get('pad_pins'):     # a15: PAD_P / PAD_N sense pins on the top edge = the control cell's PAD trunks (already on the pad nets)
                for n_ in ('PAD_P', 'PAD_N'): C.label(n_, tx[n_], Y_TOP - .5, 'metal4', True)
            if not DISC: v1, v2 = g['vcm']; C.metal(4, X_EAST - 4., v1, X_EAST, Y_TOP); C.label('TERM_VCM', X_EAST - 2., Y_TOP - .5, 'metal4', True)
            elif not nvt.get('disc2'): C.label('TERM_VCM', tx['TERM_VCM'], Y_TOP - .5, 'metal4', True)     # disconnect: the pin is the control cell's TERM_VCM trunk
            assert info['leg_N']['x'][1] + 1. < TRIM_RISER_X[0] - .6 and TRIM_RISER_X[-1] + .6 < X_EAST - 4.3
            for k, xk in enumerate(TRIM_RISER_X):
                y = g['gy'][f'TERM_TRIM{k}']
                C.metal(4, xk - .6, y - .2, xk + .6, y + .2); C.via(3, xk - .44, y - .14, xk - .16, y + .14); C.via(4, xk + .16, y - .14, xk + .44, y + .14)
                C.metal(5, xk - .5, y - .5, xk + .5, Y_TOP - .1)
                C.metal(4, xk - .5, Y_TOP - 1.72, xk + .5, Y_TOP); C.via(4, xk - .14, Y_TOP - 1.2, xk + .14, Y_TOP - .92)
                C.label(f'TERM_TRIM{k}', xk, Y_TOP - .4, 'metal4', True)
            info['top_pins'] = True
        n = 'TERM_VCM'; yv = (g['vcm'][0] + g['vcm'][1]) / 2
        if DISC: info['disc'] = (disconnect2(C, P['dis'], sch, tx, down, g, rows=int(nvt['disc2'][3]) if len(nvt['disc2']) > 3 else 1) if nvt.get('disc2') else disconnect(C, P['dis'], sch, tx, down, g))
        else: down(n, yv - .7); C.stack(4, 5, tx[n] - .5, yv - .7, tx[n] + .5, yv + .7, enc=.2); C.metal(5, tx[n] - .5, yv - .7, 22.5, yv + .7); C.stack(4, 5, 20.3, yv - .7, 22.5, yv + .7, enc=.2)
        n = 'TERM_ENABLE_LOCAL'; ye = g['gy'][n]
        down(n, ye - .2); C.stack(3, 4, tx[n] - .2, ye - .2, tx[n] + .2, ye + .2, enc=.06); C.metal(3, tx[n] - .2, ye - .2, info['leg_P']['x'][0] + .5, ye + .2)
        n = 'PAD_P'; down(n, yb1 + 9.6); C.metal(4, tx[n] - .2, yb1 + 9.6, AXIS - 105.5 - NECK_W / 2 + 1, yb1 + 10.4)
        n = 'PAD_N'; yc = yb2 + 6.; xn = AXIS + 30.
        down(n, yc - .2); C.stack(3, 4, tx[n] - .2, yc - .2, tx[n] + .2, yc + .2, enc=.06); C.metal(3, tx[n] - .2, yc - .2, xn + .2, yc + .2); C.metal(3, xn - .2, yb2 - .5, xn + .2, yc + .2)
        n = 'VSS'; ys = CTL_Y - 3.
        down(n, ys); C.stack(4, 5, tx[n] - .5, ys, tx[n] + .5, ys + 1.4, enc=.2); C.metal(5, tx[n] - .5, ys, AXIS + d['bus']['vss'][1], ys + 1.4)
        C.metal(5, AXIS + d['bus']['vss'][0], d['y'][1] - 1., AXIS + d['bus']['vss'][1], ys + 1.4)
        info['bbox_um'] = [0., 0., 2 * AXIS, Y_TOP]
    for net, x, y, layer, port in C.labels: pass
    seen = {}
    for net, x, y, layer, port in C.labels:
        C.c += [f'box values {x - .1} {y - .1} {x + .1} {y + .1}', f'label {net} FreeSans 0.3 0 0 0 c {layer}']
        if port:
            seen.setdefault(net, len(seen) + 1); C.c += [f'port make {seen[net]}']
    C.c += ['select top cell', f'flatten {top}', f'load {top}', 'select top cell', 'drc style drc(full)', 'drc check', 'drc catchup',
            'set f [open drc.txt w]', 'puts $f "DRC [drc list count total]"', 'puts $f [drc listall why]', 'close $f',
            'extract all', 'ext2spice lvs', f'ext2spice -o {top}.lvs.spice', 'ext2spice default', 'ext2spice format ngspice', 'ext2spice cthresh 0',
            'ext2spice hierarchy off', 'ext2spice subcircuit top on', 'ext2spice scale off', f'ext2spice -o {top}.ext.spice',
            f'gds write {top}.gds', 'save', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(C.c) + '\n')
    r = docker_magic(work, 'layout.tcl')
    drc = (work / 'drc.txt').read_text() if (work / 'drc.txt').exists() else 'no drc output'
    lines = ['.subckt ' + top + ' ' + ' '.join(seen)]
    for d in sch:
        if d[3] == 'DIODE': lines.append(f'D{d[0]} {d[1]} {d[2]} {d[4]} area={d[5]:g}p pj={d[6]:g}u'); continue
        if d[-3] == 'ppolyf_u': lines.append(f'X{d[0]} {d[1]} {d[2]} {d[3]} ppolyf_u r_width={d[5]}u r_length={d[6]}u')
        else: lines.append(f'X{d[0]} {d[1]} {d[2]} {d[3]} {d[4]} {d[5]} w={d[6]}u l={d[7]}u')
    if part == 'all':
        body = (work / 'ctl/pt_tx_ctl.lvs_sch.spice').read_text()
        lines += [l for l in body.splitlines() if l.startswith('X')]
        for n in ('P', 'N'):
            lines += [f'DN{n}{i} VSS PAD_{n} diode_nd2ps_06v0 area=22.5p pj=51.8u\nDP{n}{i} PAD_{n} DVDD_{n} diode_pd2nw_06v0 area=22.5p pj=51.8u' for i in range(4)]
            lines += [f'DQ{n}{i} PAD_{n} DVDD_{n} diode_pd2nw_06v0 area=22.5p pj=51.8u' for i in range(len(UP2))]
            ux = (sw6 or {}).get('upx') or (upx or {}).get('x')
            if ux: lines += [f'DV{n}{i} PAD_{n} DVDD_{n} diode_pd2nw_06v0 area=22.5p pj=51.8u' for i in range(len(ux))]
    (work / 'schematic.spice').write_text('\n'.join(lines + ['.ends']) + '\n')
    if part == 'all':
        import hs_leg_layout as hl
        res = hl.ck.lvs(work, f'{top}.lvs.spice', top, 'schematic.spice', top)
        info.update(lvs=res['final'], lvs_unique=res['match_unique'])
        sys.path.insert(0, str(HERE)); os.environ.setdefault('SVALBARD_PAD_IMAGE', 'sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43')
        from gds_markers import repair
        info['marker_export'] = repair(work, top)
        info['marker_merge'] = merge_markers(work, top)
        if nvt and nvt.get('merged'): info['nat_post'] = nat_post(work, top, info['leg_P']['nat'] + info['leg_N']['nat'], .9 if nvt.get('em') else 0.)   # em: over the upper tap strip too (DV.2)
        if sec:     # --sec: Nplus (32/0) over each cathode tap strip grown 0.16 um as one rectangle (Magic's export leaves a 0.35 um NP.1 step at the ends)
            boxes = [[g['sec']['units'][0] - 1.76, g['sec']['tap'][0] - .16, g['sec']['units'][-1] + 1.76, g['sec']['tap'][1] + .16] for g in (info['leg_P'], info['leg_N'])]
            (work / 'np.py').write_text('import klayout.db as k\n' f'l = k.Layout(); l.read("/work/{top}.gds"); c = l.cell("{top}"); li = l.layer(32, 0)\n'
                                        f'for b in {boxes!r}: c.shapes(li).insert(k.DBox(*b))\n' f'l.write("/work/{top}.gds")\n')
            subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{work}:/work',
                            IMAGE, '/work/np.py'], check=True, timeout=600)
            info['sec_nplus_boxes'] = boxes
        import hashlib
        info['gds_sha256'] = hashlib.sha256((work / f'{top}.gds').read_bytes()).hexdigest()
    info.update(drc=drc.splitlines()[0] if drc else None, instances=C.ninst, ports=list(seen))
    (work / 'layout-info.json').write_text(json.dumps(info, indent=1, default=str) + '\n')
    print(drc[:3000]); print(json.dumps({k: info.get(k) for k in ('drc', 'instances', 'lvs', 'marker_merge', 'gds_sha256')}, default=str))


if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('work', type=Path); a.add_argument('--part', default='all')
    a.add_argument('--main-scale', type=float, default=1.); a.add_argument('--post-scale', type=float, default=1.); a.add_argument('--tmds-scale', type=float, default=1.)
    a.add_argument('--sec', type=json.loads, default=None); a.add_argument('--sw6', type=json.loads, default=None); a.add_argument('--upx', type=json.loads, default=None)
    a.add_argument('--nvt', type=json.loads, default=None); a.add_argument('--top-pins', action='store_true')
    o = a.parse_args()
    generate(o.work.resolve(), o.part, dict(MAIN=o.main_scale, POST=o.post_scale, TMDS=o.tmds_scale), **(dict(sec=o.sec) if o.sec else {}), **(dict(sw6=o.sw6) if o.sw6 is not None else {}), **(dict(upx=o.upx) if o.upx else {}), **(dict(nvt=o.nvt) if o.nvt is not None else {}), **(dict(top_pins=True) if o.top_pins else {}))
