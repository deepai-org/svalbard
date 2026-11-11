#!/usr/bin/env python3
"""pt_pll_vreg layout (PDN-04 / RA-17): Magic layout, DRC (Magic + KLayout), LVS, extraction.

Uses the converter netlist-to-layout kit (analog/converters/lib/convkit.py: PCell rows, private Metal2
risers, Metal3 channel tracks, Metal4 trunks). The layout netlist is the schematic of pll_vreg.py with
these implementation mappings (electrically identical within the model; the extracted reruns below use
the drawn layout, not this mapping):
  * pass device  nfet_06v0_nvt W 20 x 300 fingers  ->  60 units of W 100 um (same total W, L 2.7 um; model bin max)
  * bypass PMOS  pfet_03v3 W 10 x 100              ->  20 units of W 50 um (L 0.28 um)
  * MOS caps     XCG 20 x 38.73^2, XCO 40 x 22.36^2 (unchanged, one guarded unit each)
  * resistors    ppolyf_u_1k_6p0 -> ppolyf_u_1k (3.3 V high-R poly; every resistor sees <= VIN <= 3.63 V),
                 split into 50 um series units (R1 6, R2 54, RB 10; ATB 20 um each)
    python3 pll_vreg_layout.py layout      # -> $PLL_VREG_WORK/layout, generated/ copies
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONV = HERE.parent / 'converters'
sys.path.insert(0, str(CONV / 'lib'))
sys.path.insert(0, str(CONV))
import convkit as ck  # noqa: E402
from convkit import Mos, Res, Circuit  # noqa: E402

N, P, NV = 'nfet_03v3', 'pfet_03v3', 'nfet_06v0_nvt'

# The 6 V native PCell draws mv* diffusion layers; alias them for convkit's pin finder (local, no kit change).
_mag_rects = ck.mag_rects


def _mag_rects_mv(path):
    r, props = _mag_rects(path)
    for a, b in (('mvndiffc', 'ndiffc'), ('mvpdiffc', 'pdiffc')):
        if a in r and b not in r:
            r[b] = r[a]
    return r, props


ck.mag_rects = _mag_rects_mv
_gencell = ck.gencell_cmd


def _gencell_nvt(key):
    # 6 V native: the kit's 3.3 V spacing overrides (diff_gate_space 0.3 ...) violate NAT.1/NAT.2/DF.3a_MV;
    # use the PCell's own 6 V defaults (guard ring, bottom contact row) instead.
    if key[0] == 'mos' and key[1] == NV:
        # NAT.1 (NAT overlaps COMP by 2 um) / NAT.2 (unrelated COMP 0.3 um outside NAT): guard ring 2.4 um from
        # the channel COMP; NAT.9: all gate poly (extension + contact head) stays inside NAT. The NAT layer itself
        # is regrown to 2 um after GDS export (Magic's NAT rule grows 0.26 um only) and DUALGATE extended over it
        # (NAT.8): nat_fix().
        return (f'magic::gencell_makecell gf180mcu::{key[1]} w {key[2]} l {key[3]} nf 1 guard 1 topc 0 botc 1 '
                'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3 diff_spacing 2.4')
    return _gencell(key)


ck.gencell_cmd = _gencell_nvt
RU = 50.           # resistor unit length (um)


def chain(name, a, b, units, l=RU, sub='VSS'):
    """Series ppolyf_u_1k units a -> b."""
    nets = [a] + [f'{name}_{k}' for k in range(1, units)] + [b]
    return [Res(f'{name}{k}', 1.0, l, nets[k], nets[k + 1], sub) for k in range(units)]


def circuit(name='pt_pll_vreg', packed=True):
    """packed=True (default, published PD28 = PD25 step 2): gate cap 30,000 -> 15,000 um2 and output cap
    20,000 -> 10,000 um2, packed into the resistor-chain rows (398 x 606 um, 0.241 mm2).
    packed=False: the PD20 layout (452 x 632 um, 0.285 mm2); build it with `layout --pd20`."""
    d = []
    # nfet_06v0_nvt model bins stop at W = 100 um per finger: 2 rows x 30 units of W 100 um
    d += [Mos(f'MPASS{k}', NV, 100., 2.7, 'VIN', 'VG', 'VOUT', 'VSS', m=30) for k in range(2)]
    d += chain('R1', 'VIN', 'INP', 6) + chain('R2', 'INP', 'VSS', 54) + chain('RB', 'VIN', 'NB', 10)
    d += [Mos('MCR', N, 10., 10., 'VSS', 'INP', 'VSS', 'VSS', m=4)]
    d += [Mos('MN1', N, 4., 1., 'X1', 'INP', 'T', 'VSS'), Mos('MN2', N, 4., 1., 'VG', 'VOUT', 'T', 'VSS'),
          Mos('MP1', P, 2., 1., 'X1', 'X1', 'VIN', 'VIN', flip=True), Mos('MP2', P, 2., 1., 'VG', 'X1', 'VIN', 'VIN', flip=True),
          Mos('MT', N, 2., 2., 'T', 'NB', 'VSS', 'VSS'), Mos('MB', N, 2., 2., 'NB', 'NB', 'VSS', 'VSS'),
          Mos('MST', P, 2., 1., 'VG', 'VOUT', 'VIN', 'VIN', flip=True)]
    d += [Mos(f'MCG{k}', N, 38.73, 38.73, 'VSS', 'VG', 'VSS', 'VSS', m=10) for k in range(2)]
    d += [Mos(f'MCO{k}', N, 22.36, 22.36, 'VSS', 'VOUT', 'VSS', 'VSS', m=mm) for k, mm in enumerate((14, 13, 13))]
    d += [Mos('MBYP', P, 50., 0.28, 'VOUT', 'BYPN', 'VIN', 'VIN', m=20, flip=True),
          Mos('MBIP', P, 4., 0.28, 'BYPN', 'BYP', 'VIN', 'VIN', flip=True), Mos('MBIN', N, 2., 0.28, 'BYPN', 'BYP', 'VSS', 'VSS')]
    d += [Res('RATO', 1.0, 20., 'VOUT', 'ATB_OUT', 'VSS'), Res('RATG', 1.0, 20., 'VG', 'ATB_G', 'VSS')]
    rows = [['MPASS0'], ['MPASS1'],
            ['MCG0'], ['MCG1'],
            ['MCO0'], ['MCO1'], ['MCO2'],
            ['MCR', 'MN1', 'MN2', 'MT', 'MB', 'MBIN'],
            [f'R1{k}' for k in range(6)] + [f'RB{k}' for k in range(10)] + ['RATO', 'RATG'] + [f'R2{k}' for k in range(54)],
            ['MP1', 'MP2', 'MST', 'MBIP', 'MBYP']]
    if packed:
        d = [x for x in d if not x.name.startswith(('MCG', 'MCO'))]
        d += [Mos(f'MCG{k}', N, 38.73, 38.73, 'VSS', 'VG', 'VSS', 'VSS', m=5) for k in range(2)]
        d += [Mos(f'MCO{k}', N, 22.36, 22.36, 'VSS', 'VOUT', 'VSS', 'VSS', m=mm) for k, mm in enumerate((7, 7, 6))]
        res = rows[8]
        rows = rows[:2] + [['MCG0'] + res[:26], ['MCG1'] + res[26:52], ['MCO0', 'MCO1'], ['MCO2'] + res[52:]] + [rows[7], rows[9]]
    c = Circuit(name, ['VIN', 'VOUT', 'VSS', 'BYP', 'ATB_OUT', 'ATB_G'], d, rows=rows,
                wide_nets={'VIN': 4.0, 'VOUT': 4.0, 'VSS': 4.0, 'VG': 1.0})
    c.notes = ['pt_pll_vreg layout netlist (pll_vreg_layout.py); schematic intent: pll_vreg.py netlist()']
    return c


NAT_FIX = r"""
import klayout.db as db
ly = db.Layout(); ly.read('CELL.gds')
nat = ly.find_layer(5, 0)
n = 0
if nat is not None:
    for cell in ly.each_cell():
        r = db.Region(cell.shapes(nat))
        if r.is_empty():
            continue
        g = r.sized(int(round(1.74 / ly.dbu))).merged()     # Magic draws 0.26 um; NAT.1 needs 2 um over COMP
        cell.shapes(nat).clear(); cell.shapes(nat).insert(g); n += 1
        dg = ly.layer(55, 0)                                   # NAT.8: DUALGATE covers NAT (6 V native)
        d = (db.Region(cell.shapes(dg)) + g).merged()
        d = d.sized(int(round(.25 / ly.dbu))).sized(-int(round(.25 / ly.dbu)))   # DV.2: close < 0.44 um gaps
        cell.shapes(dg).clear(); cell.shapes(dg).insert(d)
ly.write('CELL.gds')
print('NAT_CELLS', n)
"""

RT = r"""
export PDKPATH=/foss/pdks/gf180mcuD
cd /work && rm -rf rt2 && mkdir rt2 && cp CELL.gds rt2/ && cd rt2
printf 'crashbackups stop\ngds read CELL.gds\nload CELL\nextract all\next2spice lvs\next2spice -o CELL.gdsrt.spice\nquit -noprompt\n' > rt.tcl
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc rt.tcl > rt.log 2>&1
cp CELL.gdsrt.spice ../CELL.natfix.gdsrt.spice
"""


def nat_fix(work, name):
    """Regrow NAT to the 2 um COMP overlap in the exported GDS, then re-extract that GDS for LVS."""
    (work / 'natfix.py').write_text(NAT_FIX.replace('CELL', name))
    r = ck.docker(ck.ANALOG_IMAGE, work, 'export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH; '
                  'python3 natfix.py || klayout -b -r natfix.py', timeout=600, entry='/bin/bash')
    (work / 'natfix.log').write_text(r.stdout + r.stderr)
    (work / 'rt2.sh').write_text(RT.replace('CELL', name))
    ck.docker(ck.ANALOG_IMAGE, work, 'export PATH=/foss/tools/bin:$PATH; bash /work/rt2.sh', timeout=1800, entry='/bin/bash')
    lr = ck.lvs(work, f'{name}.natfix.gdsrt.spice', name, f'{name}.lvs_sch.spice', name, out='lvs-natfix-roundtrip.txt')
    return dict(log=(r.stdout + r.stderr)[-300:], published_gds_lvs=lr['final'], published_gds_lvs_unique=lr['match_unique'])


def work_dir():
    import os
    return Path(os.environ.get('PLL_VREG_WORK', str(HERE.parents[3] / 'scratch/pdn04-ldo'))) / 'layout'


def layout(packed=True, gen=None):
    """gen=None publishes to generated/ (canonical); a scratch gen dir builds a candidate without publishing."""
    import flow
    c = circuit(packed=packed)
    work = work_dir() if gen is None else Path(gen) / 'layout'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch = c.spice(include_macros=False)
    (HERE / 'pt_pll_vreg_layout.spice' if gen is None else Path(gen) / 'pt_pll_vreg_layout.spice').write_text('* ' + c.notes[0] + '\n' + sch)
    L = ck.Layout(c, work).build()
    L.write()
    (work / f'{c.name}.lvs_sch.spice').write_text(L.lvs_reference(sch))
    res = ck.lvs(work, f'{c.name}.lvs.spice', c.name, f'{c.name}.lvs_sch.spice', c.name)
    gx = flow.export_gds(work, c)
    gx['nat_fix'] = nat_fix(work, c.name)     # the KLayout precheck below runs on the NAT-fixed GDS
    gen = HERE / 'generated' if gen is None else Path(gen)
    gen.mkdir(exist_ok=True)
    for src, dst in ((f'{c.name}.gds', 'pt_pll_vreg.gds'), (f'{c.name}.ext.spice', 'pt_pll_vreg.ext.spice'), ('lvs.txt', 'pt_pll_vreg-lvs.txt')):
        if (work / src).exists():
            shutil.copy(work / src, gen / dst)
    pre = None
    try:
        sys.path.insert(0, str(HERE.parent))
        from gds_uniquify import publish_checked
        pre = publish_checked(gen / 'pt_pll_vreg.gds', 'pt_pll_vreg', c.name)
    except Exception as e:  # recorded
        pre = dict(error=repr(e)[:400])
    info = dict(L.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx, klayout_precheck=pre)
    (work / 'layout-info.json').write_text(json.dumps(info, indent=2, default=str) + '\n')
    (gen / 'pt_pll_vreg-layout.json').write_text(json.dumps(info, indent=2, default=str) + '\n')
    print(json.dumps({k: info[k] for k in ('drc_count', 'lvs', 'lvs_unique')}, default=str), gx.get('klayout_drc'), gx['nat_fix'], pre)
    return info


if __name__ == '__main__':
    if sys.argv[1:2] == ['layout']:
        layout(packed='--pd20' not in sys.argv, gen=next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--gen=')), None))
