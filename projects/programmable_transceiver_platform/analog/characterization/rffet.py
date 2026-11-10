#!/usr/bin/env python3
"""RF transistor test structure: nfet_03v3, W = 10 um as 5 fingers of 2 um,
L = 0.28 um, in a two-port ground-signal-ground (GSG) probe frame, plus the
OPEN and SHORT de-embedding frames (scratch/reviews/MANDATE.md device-speed
guidance; gf180-device-speed-evidence.md section 7).

Measurement: on-wafer 2-port S-parameters (GSG probes, 100 um pitch) on the
bare die before or instead of bonding; de-embed OPEN then SHORT; bias the gate
and drain through the probe bias tees (source = frame ground).  Gives fT
(|h21| = 1), fmax (Mason U = 1) and the gate resistance (Re Z11 slope), i.e.
the three numbers the 2.4 GHz and CML designs rely on.

Device (one Magic PCell, gf180mcu::nfet_03v3 w 2 nf 5): poly gate contacted at
both finger ends (top and bottom), gate_to_polycont 0.8 um so a continuous
Metal1 gate bar fits on each side; diffusion columns alternate S D S D S D.
Drains rise on Metal3 to a drain bus above the device, sources fall to a source
bus below it, and the guard ring (body) joins the source bus.

Frame (all cells identical outside the DUT window): six 60 x 60 um Metal5 pads
with 50 x 50 um passivation openings (GLASS), 100 um pitch.
    gate port  (x = -150 um): G (y = +100), S = gate (y = 0), G (y = -100)
    drain port (x = +150 um): G, S = drain, G
Grounds: 28 um Metal5 strips (under the 30 um slotting limit) join the top and bottom G pads (y = +-100) and two
Metal5 side rails (x = +-205 um) join the strips.  The source/body reaches the
bottom strip on Metal3 -> Metal5.  Gate and drain leads are Metal4 (4 um).
    pt_char_rffet        DUT
    pt_char_rffet_open   leads end at the DUT window, no device
    pt_char_rffet_short  gate and drain leads shorted to the source bus

    python3 rffet.py layout     # three cells: DRC, extraction, LVS (DUT), GDS + KLayout DRC, LEF
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'converters' / 'lib'))
sys.path.insert(0, str(HERE.parent / 'converters'))
import convkit as ck  # noqa: E402

ROOT = HERE.parents[3]
WORK = ROOT / 'scratch' / 'characterization' / 'speed' / 'rffet'
GEN = HERE / 'generated'
CELLS = ['pt_char_rffet', 'pt_char_rffet_open', 'pt_char_rffet_short']
PAD = 60.0
GLASS = 50.0
PITCH = 100.0
XP = 150.0          # pad column centres at +-XP
XR = 205.0          # ground side rails
VP = 0.8            # via array pitch


class T:
    def __init__(self):
        self.c = []

    def box(self, layer, x1, y1, x2, y2):
        q = ck.q
        self.c.append(f'box values {q(min(x1, x2))} {q(min(y1, y2))} {q(max(x1, x2))} {q(max(y1, y2))}')
        self.c.append(f'paint {layer}')

    def vias(self, lo, hi, x1, y1, x2, y2):
        """Metal lo..hi over the rectangle, with via arrays on every level."""
        for m in range(lo, hi + 1):
            self.box(f'metal{m}', x1, y1, x2, y2)
        cut = {1: 0.26, 2: 0.28, 3: 0.28, 4: 0.28}
        enc = 0.2
        for m in range(lo, hi):
            s = cut[m]
            nx = max(1, int((x2 - x1 - 2 * enc - s) // VP) + 1)
            ny = max(1, int((y2 - y1 - 2 * enc - s) // VP) + 1)
            ox = ck.q((x1 + x2) / 2 - (nx - 1) * VP / 2)
            oy = ck.q((y1 + y2) / 2 - (ny - 1) * VP / 2)
            for i in range(nx):
                for j in range(ny):
                    cx, cy = ox + i * VP, oy + j * VP
                    self.box(f'via{m}', cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2)


def frame(t, kind):
    """Pads, grounds and leads.  Returns label positions."""
    for sx in (-1, 1):
        for yc in (-PITCH, 0.0, PITCH):
            x, y = sx * XP, yc
            t.box('metal5', x - PAD / 2, y - PAD / 2, x + PAD / 2, y + PAD / 2)
            t.box('glass', x - GLASS / 2, y - GLASS / 2, x + GLASS / 2, y + GLASS / 2)
    # ground strips and side rails (Metal5)
    for sy in (-1, 1):
        t.box('metal5', -XR - 10, sy * PITCH - 14, XR + 10, sy * PITCH + 14)     # <= 30 um: no slotting (MSLOT5.1)
    for sx in (-1, 1):
        t.box('metal5', sx * XR - 10, -PITCH - 14, sx * XR + 10, PITCH + 14)
    # gate lead: Metal4 from the gate pad to x = -8; drain lead Metal4 from x = +8 to the drain pad
    t.vias(4, 5, -XP - 20, -2, -XP + 20, 2)
    t.box('metal4', -XP, -2, -8, 2)
    t.vias(4, 5, XP - 20, -2, XP + 20, 2)
    t.box('metal4', 8, -2, XP, 2)
    # source lead: Metal3 from the source bus (y = -6) down to the bottom ground strip
    t.box('metal3', -2, -PITCH + 20, 2, -6)
    t.vias(3, 5, -6, -PITCH, 6, -PITCH + 20)
    # gate lead end: metal2..4 stack at x = -8..-6, drain end at 6..8
    t.vias(2, 4, -10, -2, -6, 2)
    t.vias(3, 4, 6, -2, 10, 2)
    if kind == 'short':
        # gate end and drain end tied to the source bus with Metal3 straps
        t.box('metal3', -10, -7, -6, 2)
        t.box('metal3', 6, -7, 10, 2)
        t.box('metal3', -10, -7, 10, -5)


DUT_TCL = r'''
set c [magic::gencell_makecell gf180mcu::nfet_03v3 w 2 l 0.28 nf 5 guard 1 topc 1 botc 1 full_metal 1 gate_to_polycont 0.8 gate_to_diffcont 0.45]
load $c
save rf_dev
'''


def dut(t, geom):
    """Routing on the PCell (instance at the origin).  geom: parsed rects."""
    cols = sorted(geom['ndiffc'], key=lambda r: r[0])
    pcs = geom['polycontact']
    top = [p for p in pcs if p[1] > 0]
    bot = [p for p in pcs if p[1] < 0]
    gx1 = min(p[0] for p in pcs) - 0.055
    gx2 = max(p[2] for p in pcs) + 0.055
    col_top = max(c[3] for c in cols) + 0.055
    # gate bars (Metal1) between the column metal and the guard-ring metal
    ytop_hi = max(p[3] for p in top)
    ybot_lo = min(p[1] for p in bot)
    t.box('metal1', gx1, col_top + 0.23, gx2, ytop_hi)
    t.box('metal1', gx1, ybot_lo, gx2, -(col_top + 0.23))
    gy = (col_top + 0.23 + ytop_hi) / 2
    # gate escape: via1 at the left end of each bar, Metal2 out to x = -8 (gate lead)
    vx = gx1 + 0.25
    for sy in (1, -1):
        t.box('via1', vx - 0.13, sy * gy - 0.13, vx + 0.13, sy * gy + 0.13)
        t.box('metal2', -8.5, sy * gy - 0.2, vx + 0.2, sy * gy + 0.2)
    t.box('metal2', -8.5, -gy - 0.2, -7.5, gy + 0.2)
    t.box('metal2', -10, -2, -7.5, 2)
    # diffusion columns: widen the Metal1, via1 + via2 at the centre, Metal3 stripes
    for i, c in enumerate(cols):
        xc = (c[0] + c[2]) / 2
        t.box('metal1', xc - 0.2, c[1] - 0.055, xc + 0.2, c[3] + 0.055)
        t.box('via1', xc - 0.13, -0.13, xc + 0.13, 0.13)
        t.box('metal2', xc - 0.2, -0.2, xc + 0.2, 0.2)
        t.box('via2', xc - 0.14, -0.14, xc + 0.14, 0.14)
        if i % 2 == 0:      # source: down to the source bus
            t.box('metal3', xc - 0.2, -6.5, xc + 0.2, 0.2)
        else:               # drain: up to the drain bus
            t.box('metal3', xc - 0.2, -0.2, xc + 0.2, 6.5)
    xs = [(c[0] + c[2]) / 2 for c in cols]
    t.box('metal3', min(xs) - 0.2, -7, max(xs) + 0.2, -5.5)        # source bus
    t.box('metal3', min(xs) - 0.2, 5.5, max(xs) + 0.2, 7)          # drain bus
    t.box('metal3', max(xs) - 0.2, 5.5, 8, 7)                       # to the drain lead end
    t.box('metal3', 6, -2, 8, 7)
    # guard ring (body) to the source bus: Metal1 patch under the bottom guard bar, via1/via2 stack
    gb = min((r for r in geom['metal1'] if r[2] - r[0] > 3), key=lambda r: r[1])
    t.box('metal1', -0.6, gb[1] - 0.3, 0.6, gb[3])
    t.box('via1', -0.13, gb[1] - 0.15 - 0.13, 0.13, gb[1] - 0.15 + 0.13)
    t.box('metal2', -0.3, -6.3, 0.3, gb[1] - 0.15 + 0.2)
    t.box('via2', -0.14, -6.04, 0.14, -5.76)
    t.box('metal3', -0.3, -6.3, 0.3, -5.5)


def parse(mag):
    r, _ = ck.mag_rects(mag)
    return r


LAYOUT_TCL = '''crashbackups stop
{body}
quit -noprompt
'''


def layout():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    # 1. device PCell
    (WORK / 'dev.tcl').write_text('crashbackups stop\nload ws\nunits internal\n' + DUT_TCL + 'quit -noprompt\n')
    r = ck.docker(ck.DIGITAL_IMAGE, WORK, f'magic -dnull -noconsole -rcfile {ck.PDK}/libs.tech/magic/gf180mcuD.magicrc /work/dev.tcl')
    (WORK / 'dev.log').write_text(r.stdout + r.stderr)
    geom = parse(WORK / 'rf_dev.mag')
    out = {}
    for cell in CELLS:
        kind = cell.split('_')[-1] if cell != 'pt_char_rffet' else 'dut'
        t = T()
        t.c += ['crashbackups stop', f'load {cell}', 'units microns']
        if kind == 'dut':
            t.c += ['getcell rf_dev child 0 0 parent 0 0', 'select clear']
            dut(t, geom)
        frame(t, kind)
        ports = {'dut': [('G', -XP, 0), ('D', XP, 0), ('GND', 0, PITCH)],
                 'open': [('G', -XP, 0), ('D', XP, 0), ('GND', 0, PITCH)],
                 'short': [('GND', 0, PITCH)]}[kind]
        for i, (p, x, y) in enumerate(ports):
            t.c += [f'box values {x} {y} {x} {y}', f'label {p} FreeSans 2 0 0 0 c metal5', f'port make {i + 1}']
        t.c += ['select top cell', 'save',
                'drc on', 'drc check', 'drc catchup',
                f'set f [open {cell}-drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
                f'set f [open {cell}-drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
                'extract all', 'ext2spice lvs', f'ext2spice -o {cell}.lvs.spice',
                'ext2spice default', 'ext2spice format ngspice', 'ext2spice cthresh 0', 'ext2spice scale off',
                f'ext2spice -o {cell}.ext.spice',
                'select top cell', f'lef write {cell}.lef -hide']
        (WORK / f'{cell}.tcl').write_text('\n'.join(t.c) + '\nquit -noprompt\n')
        r = ck.docker(ck.DIGITAL_IMAGE, WORK, f'magic -dnull -noconsole -rcfile {ck.PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{cell}.tcl')
        (WORK / f'{cell}.log').write_text(r.stdout + r.stderr)
        drc = (WORK / f'{cell}-drc-count.txt').read_text().strip() if (WORK / f'{cell}-drc-count.txt').exists() else None
        out[cell] = dict(kind=kind, magic_drc=int(drc) if drc and drc.isdigit() else drc)
    # 2. LVS of the DUT against its one-device schematic
    sch = '.subckt pt_char_rffet G D GND\nXM D G GND GND nfet_03v3 w=2u l=0.28u nf=5\n.ends\n'
    sch_m = '.subckt pt_char_rffet G D GND\n' + ''.join(f'XM{i} D G GND GND nfet_03v3 w=2u l=0.28u\n' for i in range(5)) + '.ends\n'
    (WORK / 'pt_char_rffet.lvs_sch.spice').write_text(sch_m)
    (HERE / 'pt_char_rffet.spice').write_text('* generated by rffet.py; do not edit\n' + sch_m)
    res = ck.lvs(WORK, 'pt_char_rffet.lvs.spice', 'pt_char_rffet', 'pt_char_rffet.lvs_sch.spice', 'pt_char_rffet')
    out['pt_char_rffet'].update(lvs=res['final'], lvs_unique=res['match_unique'])
    # open/short: connectivity from the extracted netlist
    for cell in CELLS[1:]:
        txt = (WORK / f'{cell}.lvs.spice').read_text() if (WORK / f'{cell}.lvs.spice').exists() else ''
        hdr = re.search(r'^\.subckt (\S+) (.*)$', txt, re.M)
        out[cell]['extracted_ports'] = hdr.group(2).split() if hdr else None
        out[cell]['devices'] = len([l for l in txt.splitlines() if l.startswith('X') or l.startswith('M')])
    (WORK / 'result.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def export():
    """Analog-image GDS + KLayout DRC + round-trip LVS (DUT) via converters/flow.export_gds."""
    import flow as convflow
    out = json.loads((WORK / 'result.json').read_text())
    for cell in CELLS:
        c = ck.Circuit(cell, [], [])
        if cell == 'pt_char_rffet':
            c = ck.Circuit(cell, ['G', 'D', 'GND'], [ck.Mos('M', 'nfet_03v3', 2.0, 0.28, d='D', g='G', s='GND', b='GND', m=5)])
        else:
            (WORK / f'{cell}.lvs_sch.spice').write_text(f'.subckt {cell}\n.ends\n')
        gx = convflow.export_gds(WORK, c)
        out[cell]['gds_export'] = gx
        short = cell.replace('pt_', '')
        for src, dst in [(f'{cell}.gds', f'{short}.gds'), (f'{cell}.lef', f'{short}.lef'), (f'{cell}.ext.spice', f'{short}.ext.spice'),
                         (f'{cell}.lvs.spice', f'{short}.lvs.spice'), (f'{cell}-drc-details.txt', f'{short}-drc.txt')]:
            if (WORK / src).exists():
                shutil.copy(WORK / src, GEN / dst)
        if cell == 'pt_char_rffet' and (WORK / 'lvs.txt').exists():
            shutil.copy(WORK / 'lvs.txt', GEN / 'char_rffet-lvs.txt')
        print(cell, 'klayout', gx['klayout_drc'], 'rt', gx.get('published_gds_lvs'), flush=True)
    import speed
    for cell in CELLS:
        short = cell.replace('pt_', '')
        out[cell]['gds_subcells_uniquified'] = speed.uniquify(GEN / f'{short}.gds')
    out['pt_char_rffet']['published_gds_after_rename'] = speed.verify_gds(GEN / 'char_rffet.gds', 'pt_char_rffet',
                                                                          WORK / 'pt_char_rffet.lvs_sch.spice')
    (GEN / 'char_rffet-physical.json').write_text(json.dumps(out, indent=1, default=str) + '\n')
    (WORK / 'result.json').write_text(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    if sys.argv[1] == 'layout':
        layout()
    elif sys.argv[1] == 'export':
        export()
