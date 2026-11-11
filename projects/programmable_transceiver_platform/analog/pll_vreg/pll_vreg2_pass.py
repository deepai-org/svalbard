#!/usr/bin/env python3
"""pt_vreg_pass (PD33): the pass device of pt_pll_vreg2 as a hand-strapped macro.

nfet_06v0_nvt W 100 / L 2.7, nf = 60 in ONE native PCell (Magic gf180mcu PCell, same 6 V native options as
pll_vreg_layout._gencell_nvt). The PCell does not strap its fingers (nf = 5 extracts as 5 devices), so this adds
  * a Metal1 gate bar over the bottom polycontact row,
  * two Via1/Metal2 bars on the even (S) columns at y -45..-40 / -15..-10 and two on the odd (D) columns at
    10..15 / 40..45 (PCell coordinates),
  * Metal2 edge pins for convkit: D north, S / G / B south (B on the left guard-ring contact column).
Outputs (default generated/pt_vreg_pass/): .gds, .lef, .pnl.v (pin order), .spice (LVS reference), drc.txt, macro LVS.
Size 199.08 x 102.92 um (60 single-finger PCells as drawn in pt_pll_vreg: 0.058 mm2).
    python3 pll_vreg2_pass.py [<out dir>]
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'converters' / 'lib'))
import convkit as ck  # noqa: E402
U = 0.005
DX, DY = 99.54, 51.46
BW, BH = 2 * DX, 2 * DY


def default_dir():
    return HERE / 'generated' / 'pt_vreg_pass'


def reference_spice():
    return '.subckt pt_vreg_pass D G S B\n' + ''.join(
        f'XM{k} {"D" if k % 2 else "S"} G {"S" if k % 2 else "D"} B nfet_06v0_nvt w=100u l=2.7u\n' for k in range(60)) + '.ends pt_vreg_pass\n'


def build(W=None):
    W = Path(W or default_dir()); W.mkdir(parents=True, exist_ok=True)
    cols = [-96.6 + 3.22 * k for k in range(61)]
    def iu(v): return int(round(v / U))
    cmds = ['crashbackups stop', 'snap internal',
            'set c [magic::gencell_makecell gf180mcu::nfet_06v0_nvt w 100 l 2.7 nf 60 guard 1 topc 0 botc 1 full_metal 1 '
            'gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3 diff_spacing 2.4]',
            'load pt_vreg_pass', f'getcell $c child 0 0 parent {iu(DX)} {iu(DY)}']
    def paint(layer, x1, y1, x2, y2):
        if layer == 'via1':   # V1.3: M1 encloses Via1 by >= 0.06 in one direction (pad M1 0.08 all round)
            cmds.append(f'box values {iu(x1-0.08+DX)} {iu(y1-0.08+DY)} {iu(x2+0.08+DX)} {iu(y2+0.08+DY)}'); cmds.append('paint metal1'); cmds.append('paint metal2')
        cmds.append(f'box values {iu(x1+DX)} {iu(y1+DY)} {iu(x2+DX)} {iu(y2+DY)}'); cmds.append(f'paint {layer}')
    # gate bar (M1 over the polycontact row)
    paint('metal1', -96.3, -50.715, 96.3, -50.485)
    # S (even columns) bars at y -45..-40 and -15..-10, D (odd) bars at 10..15 and 40..45
    bars = {'S': [(-45, -40), (-15, -10)], 'D': [(10, 15), (40, 45)]}
    for net, ys in bars.items():
        for y1, y2 in ys:
            paint('metal2', -97.0, y1, 97.0, y2)
            for k, x in enumerate(cols):
                if (k % 2 == 0) == (net == 'S'):
                    paint('via1', x - 0.19, y1 + 0.3, x + 0.19, y2 - 0.3)
    # pins
    pins = {}
    xg, xs, xd, xb = -1.61, 1.61, 1.61, -99.36
    paint('via1', xg - 0.19, -50.79, xg + 0.19, -50.41); paint('metal2', xg - 0.2, -DY, xg + 0.2, -50.41); pins['G'] = (xg, 'S')
    paint('metal2', xs - 0.2, -DY, xs + 0.2, -40); pins['S'] = (xs, 'S')
    paint('metal2', xd - 0.2, 40, xd + 0.2, DY); pins['D'] = (xd, 'N')
    paint('via1', xb - 0.11, -48.4, xb + 0.15, -48.0); paint('metal2', xb - 0.2, -DY, xb + 0.2, -48.0); pins['B'] = (xb, 'S')
    for n, (x, e) in pins.items():
        y1, y2 = (-DY, -DY + 0.6) if e == 'S' else (DY - 0.6, DY)
        cmds.append(f'box values {iu(x-0.2+DX)} {iu(y1+DY)} {iu(x+0.2+DX)} {iu(y2+DY)}')
        cmds.append(f'label {n} FreeSans 0 0 0 0 center metal2'); cmds.append(f'port make')
    cmds += ['select top cell', 'save pt_vreg_pass', 'drc on', 'drc check', 'drc catchup',
             'set f [open drc.txt w]', 'puts $f [drc list count total]', 'puts $f [drc listall why]', 'close $f',
             'extract all', 'ext2spice lvs', 'ext2spice -o pt_vreg_pass.lvs.spice', 'gds write pt_vreg_pass.gds', 'quit -noprompt']
    for f in list(W.glob('*.mag')) + list(W.glob('*.ext')):
        f.unlink()
    (W / 'macro.tcl').write_text('\n'.join(cmds) + '\n')
    r = ck.docker(ck.ANALOG_IMAGE, W, 'export PATH=/foss/tools/bin:$PATH PDKPATH=/foss/pdks/gf180mcuD; '
                  'magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc macro.tcl > macro.log 2>&1', timeout=1800, entry='/bin/bash')
    print(r.returncode, (W / 'drc.txt').read_text()[:1500] if (W / 'drc.txt').exists() else 'no drc')
    # LEF / verilog / reference subckt
    lef = [f'MACRO pt_vreg_pass', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', f'  SIZE {BW:.3f} BY {BH:.3f} ;']
    for n, (x, e) in pins.items():
        y1, y2 = (0, 0.6) if e == 'S' else (BH - 0.6, BH)
        lef += [f'  PIN {n}', '    DIRECTION INOUT ;'] + (['    ANTENNAGATEAREA 16200.0 ;'] if n == 'G' else []) + \
               ['    PORT', '      LAYER Metal2 ;', f'        RECT {x-0.2+DX:.3f} {y1:.3f} {x+0.2+DX:.3f} {y2:.3f} ;', '    END', f'  END {n}']
    lef += ['END pt_vreg_pass', 'END LIBRARY']
    (W / 'pt_vreg_pass.lef').write_text('\n'.join(lef) + '\n')
    (W / 'pt_vreg_pass.pnl.v').write_text('module pt_vreg_pass (D, G, S, B);\n  inout D;\n  inout G;\n  inout S;\n  inout B;\nendmodule\n')
    (W / 'pt_vreg_pass.spice').write_text(reference_spice())
    r = ck.lvs(W, 'pt_vreg_pass.lvs.spice', 'pt_vreg_pass', 'pt_vreg_pass.spice', 'pt_vreg_pass')
    drc = (W / 'drc.txt').read_text().split('\n')[0].strip()
    return dict(drc=int(drc), lvs=r['final'], lvs_unique=r['match_unique'], size_um=[BW, BH])


if __name__ == '__main__':
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
