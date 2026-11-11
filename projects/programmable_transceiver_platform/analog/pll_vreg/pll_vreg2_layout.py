#!/usr/bin/env python3
"""pt_pll_vreg2 (PD33, coordinator-approved 2026-11-11): one dual-output ring regulator for pll_tx and pll_cdr.

One reference divider (30k/270k), one slow OTA and one gate cap (30,000 um2) hold a shared gate VG; two native
followers (nfet_06v0_nvt W 6000 / L 2.7 each) drive VOUT_TX (inside the OTA loop) and VOUT_CDR (open loop on the
same VG); each output has its own 3,000 um2 MOS cap and its own BYP PMOS (W 1000 um). The rings couple only through
VG (Cgd / Cg), never through a shared output.

Each pass device is the hand-strapped macro `pt_vreg_pass` (pll_vreg2_pass.py: one nf = 60 native PCell, the
fingers strapped with a Metal1 gate bar and Via1/Metal2 source/drain bars; 199 x 103 um instead of 0.058 mm2 for
60 single-finger PCells). Everything else is the convkit flow of pll_vreg_layout.py.
    python3 pll_vreg2_layout.py layout [--gen=<dir>]     # default gen = generated/
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pll_vreg_layout as pl  # noqa: E402  (convkit setup, nat_fix)
import pll_vreg2_pass as pp  # noqa: E402

ck = pl.ck
Mos, Res, Circuit = ck.Mos, ck.Res, ck.Circuit
N, P = 'nfet_03v3', 'pfet_03v3'
PORTS = ['VIN', 'VOUT_TX', 'VOUT_CDR', 'VSS', 'BYP_TX', 'BYP_CDR', 'ATB_OUT', 'ATB_G']


def circuit(name='pt_pll_vreg2', macro_dir=None):
    m = Path(macro_dir or pp.default_dir())
    mac = lambda n, s: ck.Macro(n, 'pt_vreg_pass', m / 'pt_vreg_pass.gds', m / 'pt_vreg_pass.lef',  # noqa: E731
                                m / 'pt_vreg_pass.pnl.v', dict(D='VIN', G='VG', S=s, B='VSS'))
    d = [mac('MPA', 'VOUT_TX'), mac('MPB', 'VOUT_CDR')]
    d += pl.chain('R1', 'VIN', 'INP', 1, l=30.) + pl.chain('R2', 'INP', 'VSS', 9, l=30.) + pl.chain('RB', 'VIN', 'NB', 17, l=30.)
    d += [Mos('MCR', N, 10., 10., 'VSS', 'INP', 'VSS', 'VSS', m=4)]
    d += [Mos('MN1', N, 4., 1., 'X1', 'INP', 'T', 'VSS'), Mos('MN2', N, 4., 1., 'VG', 'VOUT_TX', 'T', 'VSS'),
          Mos('MP1', P, 2., 1., 'X1', 'X1', 'VIN', 'VIN', flip=True), Mos('MP2', P, 2., 1., 'VG', 'X1', 'VIN', 'VIN', flip=True),
          Mos('MT', N, 2., 2., 'T', 'NB', 'VSS', 'VSS'), Mos('MB', N, 2., 2., 'NB', 'NB', 'VSS', 'VSS'),
          Mos('MST', P, 2., 1., 'VG', 'VOUT_TX', 'VIN', 'VIN', flip=True)]
    d += [Mos(f'MCG{k}', N, 38.73, 38.73, 'VSS', 'VG', 'VSS', 'VSS', m=mm) for k, mm in enumerate((9, 9, 2))]
    d += [Mos('MCOA', N, 38.73, 38.73, 'VSS', 'VOUT_TX', 'VSS', 'VSS', m=2),
          Mos('MCOB', N, 38.73, 38.73, 'VSS', 'VOUT_CDR', 'VSS', 'VSS', m=2)]
    for s, o in (('TX', 'VOUT_TX'), ('CDR', 'VOUT_CDR')):
        d += [Mos(f'MBYP{s}', P, 50., 0.28, o, f'BYPN_{s}', 'VIN', 'VIN', m=20, flip=True),
              Mos(f'MBIP{s}', P, 4., 0.28, f'BYPN_{s}', f'BYP_{s}', 'VIN', 'VIN', flip=True),
              Mos(f'MBIN{s}', N, 2., 0.28, f'BYPN_{s}', f'BYP_{s}', 'VSS', 'VSS')]
    d += [Res('RATO', 1.0, 20., 'VOUT_TX', 'ATB_OUT', 'VSS'), Res('RATG', 1.0, 20., 'VG', 'ATB_G', 'VSS')]
    rows = [['MPA', 'MPB'],
            ['MCG0'], ['MCG1'],
            ['MCOA', 'MCOB', 'MCR', 'MN1', 'MN2', 'MT', 'MB', 'MBINTX', 'MBINCDR', 'R10'] + [f'R2{k}' for k in range(9)]
            + [f'RB{k}' for k in range(17)] + ['RATO', 'RATG'],
            ['MCG2', 'MP1', 'MP2', 'MST', 'MBIPTX', 'MBIPCDR', 'MBYPTX', 'MBYPCDR']]
    c = Circuit(name, PORTS, d, rows=rows, wide_nets={'VIN': 4.0, 'VOUT_TX': 4.0, 'VOUT_CDR': 4.0, 'VSS': 4.0, 'VG': 1.0})
    c.notes = ['pt_pll_vreg2 layout netlist (pll_vreg2_layout.py); dual-output PD33']
    return c


def schematic(c):
    """LVS / simulation reference: convkit netlist + the pass macro subckt."""
    return c.spice(include_macros=False) + '\n' + pp.reference_spice()


def layout(gen=None, macro_dir=None):
    import flow
    c = circuit(macro_dir=macro_dir)
    gen = Path(gen) if gen else HERE / 'generated'
    work = gen / 'layout2' if gen != HERE / 'generated' else pl.work_dir().parent / 'layout2'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch = schematic(c)
    (gen / 'pt_pll_vreg2_layout.spice').write_text('* ' + c.notes[0] + '\n' + sch)
    L = ck.Layout(c, work).build()
    L.write()
    (work / f'{c.name}.lvs_sch.spice').write_text(L.lvs_reference(sch))
    res = ck.lvs(work, f'{c.name}.lvs.spice', c.name, f'{c.name}.lvs_sch.spice', c.name)
    gx = flow.export_gds(work, c)
    gx['nat_fix'] = pl.nat_fix(work, c.name)
    gen.mkdir(exist_ok=True, parents=True)
    for src, dst in ((f'{c.name}.gds', 'pt_pll_vreg2.gds'), (f'{c.name}.ext.spice', 'pt_pll_vreg2.ext.spice'),
                     ('lvs.txt', 'pt_pll_vreg2-lvs.txt')):
        if (work / src).exists():
            shutil.copy(work / src, gen / dst)
    pre = None
    try:
        sys.path.insert(0, str(HERE.parent))
        from gds_uniquify import publish_checked
        pre = publish_checked(gen / 'pt_pll_vreg2.gds', 'pt_pll_vreg2', c.name)
    except Exception as e:  # recorded
        pre = dict(error=repr(e)[:400])
    info = dict(L.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx, klayout_precheck=pre)
    (gen / 'pt_pll_vreg2-layout.json').write_text(json.dumps(info, indent=2, default=str) + '\n')
    print(json.dumps({k: info.get(k) for k in ('drc_count', 'lvs', 'lvs_unique', 'bbox_um', 'area_um2')}, default=str),
          gx.get('klayout_drc'), gx['nat_fix'], pre)
    return info


if __name__ == '__main__':
    if sys.argv[1:2] == ['layout']:
        layout(gen=next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--gen=')), None),
               macro_dir=next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--macro=')), None))
