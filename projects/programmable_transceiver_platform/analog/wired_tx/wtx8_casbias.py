"""wtx8_casbias: CASCODE supply for pad_txpad's cascode gates (WT53-c / WT54), on RAIL_wired_tx (block VDD).  NOT published.

    CB_EN (= wtx.cascode_boost, reset 0)   CASCODE -> pad_txpad CASCODE pins (0.3 pF gate load, no DC)

  CB_EN = 0: select switch MS (pfet_06v0, well = CASCODE) on: CASCODE = VDD (about 150 ohm); ring oscillator stopped,
             both pump clocks held low, so both flying nodes sit at or below VDD and the pump cannot push charge out.
  CB_EN = 1: MS off (gate lifted to CASCODE by a level shifter supplied from CASCODE); a 5-stage ring oscillator
             (NAND + 4 inverters, L = 1 um) clocks a cross-coupled voltage doubler (MN1/MN2 nfet_06v0 from VDD, MP1/MP2
             pfet_06v0 to CASCODE, flying caps CF1 / CF2 = 6 x 6 um pfet_06v0 MOS caps, gate on the
             clock, drain / source / well on the flying node); CASCODE is regulated by the replica shunt MR, a
             pfet_06v0 diode from CASCODE into VDD (well = CASCODE):  CASCODE = VDD + Vsg(MR at the pump's few uA).
             The shunt is also the clamp: the pump's current is bounded (f x C_fly), so CASCODE cannot exceed
             VDD + Vsg(MR at that current); schematic: <= 4.53 V at ff 0 C 3.63 V (limit 4.6).
             Output reservoir: 1 pF nfet_06v0 gate capacitor (ripple).
  Replica note: the brief's reference is "VDD + Vt(nfet_06v0) + 0.2 V".  An nfet_06v0 diode sitting above VDD carries
  about 0.6-0.8 V of body effect (Vsb = VDD; measured 1.4-1.7 V Vgs at 2 uA), so the shunt uses a 6 V PMOS in its own
  well (no body effect) whose Vsg at a few uA (0.9-1.1 V) lands on the 4.2 V target and tracks the process corner.
  Flying caps (2026-11-24): the first layout used nfet_06v0 caps (gate = flying node, channel = clock, body = VSS); with
  the clock high the channel sits at VDD, the body effect lifts Vt to about 1.7 V at ss, the cap drops out of inversion
  during start-up (flying nodes only precharged to VDD - Vt) and the pump never started at ss (extracted: CASCODE 3.14 V
  at ss 3.15 V). A pfet cap with its well on the flying node has no body effect and stays inverted while F - CK > |Vtp|.
  Extracted (scratch/wired_tx/s18/tran/ext_*.json, 0.3 pF load): ss 32 C 3.15 V 4.12 V (start 0.50 us); ss 85 C 2.97 V
  3.84 V; tt 27 C 3.3 V 4.20 V; ff 0 C 3.63 V 4.48 V (limit 4.6); negative control without MR at ff: 5.50 V (fails, as
  it must).  Layout: CF1 / CF2 in separate rows (NW.2b_MV well spacing).
  Every node above 3.6 V is on 6 V devices only (CASCODE, F1 / F2, SG / SGB); 3.3 V devices see 0..VDD.

    python3 wtx8_casbias.py            # writes generated/fast/wtx8_casbias.spice (schematic)
    python3 wtx8_casbias.py layout     # convkit layout + DRC / LVS -> scratch/wired_tx/s18/casbias
"""
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONV = HERE.parent / 'converters'
sys.path.insert(0, str(CONV / 'lib'))
sys.path.insert(0, str(CONV))
import convkit as ck  # noqa: E402
from convkit import Mos  # noqa: E402

# 6 V PCells draw mv* diffusion contacts: alias them for convkit's pin finder, and let the 6 V PCells keep their own
# diffusion-to-gate spacing (the kit's 3.3 V override violates the MV rules); as pll_vreg_layout.py (local, no kit change)
_mag_rects, _gencell = ck.mag_rects, ck.gencell_cmd


def _mag_rects_mv(path):
    r, props = _mag_rects(path)
    for a, b in (('mvndiffc', 'ndiffc'), ('mvpdiffc', 'pdiffc')):
        if a in r and b not in r:
            r[b] = r[a]
    return r, props


def _gencell_mv(key):
    if key[0] == 'mos' and key[1].endswith('06v0'):
        return (f'magic::gencell_makecell gf180mcu::{key[1]} w {key[2]} l {key[3]} nf 1 guard 1 topc 0 botc 1 '
                'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8')
    return _gencell(key)


ck.mag_rects, ck.gencell_cmd = _mag_rects_mv, _gencell_mv

NAME = 'wtx8_casbias'
PORTS = ['CB_EN', 'CASCODE', 'VDD', 'VSS']
N3, P3, N6, P6 = 'nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0'
FAST = HERE / 'generated' / 'fast'
WORK = HERE.parents[3] / 'scratch' / 'wired_tx' / 's18' / 'casbias'
SIZE = dict(lring=1.0, cfly=6.0, cout=14.7, ncout=2, wr=10.0, lr=0.55, nr=5, ws=5.0, ns=4)


def devices(z=SIZE):
    d = []

    def inv(n, a, y, wn=1.0, wp=2.0, l=0.28):
        return [Mos(n + 'n', N3, wn, l, y, a, 'VSS', 'VSS'), Mos(n + 'p', P3, wp, l, y, a, 'VDD', 'VDD')]

    def nand(n, a, b, y, l):
        return [Mos(n + 'na', N3, 1.0, l, y, a, n + 'm', 'VSS'), Mos(n + 'nb', N3, 1.0, l, n + 'm', b, 'VSS', 'VSS'),
                Mos(n + 'pa', P3, 2.0, l, y, a, 'VDD', 'VDD'), Mos(n + 'pb', P3, 2.0, l, y, b, 'VDD', 'VDD')]

    def nor(n, a, b, y):
        return [Mos(n + 'na', N3, 1.0, 0.28, y, a, 'VSS', 'VSS'), Mos(n + 'nb', N3, 1.0, 0.28, y, b, 'VSS', 'VSS'),
                Mos(n + 'pb', P3, 2.0, 0.28, n + 'm', b, 'VDD', 'VDD'), Mos(n + 'pa', P3, 2.0, 0.28, y, a, n + 'm', 'VDD')]
    # enable, ring, clock phases (3.3 V)
    d += inv('I0', 'CB_EN', 'ENB') + inv('I1', 'ENB', 'EN')
    d += nand('R0', 'EN', 'R4', 'R0', z['lring'])
    for k in range(1, 5):
        d += inv(f'R{k}', f'R{k - 1}', f'R{k}', l=z['lring'])
    d += nor('PA', 'ENB', 'R3', 'PA') + nor('PB', 'ENB', 'R4', 'PB')
    d += inv('BA1', 'PA', 'PAB') + inv('BA2', 'PAB', 'CKA', 2.0, 4.0) + inv('BB1', 'PB', 'PBB') + inv('BB2', 'PBB', 'CKB', 2.0, 4.0)
    # doubler (6 V)
    d += [Mos('MN1', N6, 1.0, 0.7, 'F1', 'F2', 'VDD', 'VSS'), Mos('MN2', N6, 1.0, 0.7, 'F2', 'F1', 'VDD', 'VSS'),
          Mos('MP1', P6, 1.0, 0.55, 'F1', 'F2', 'CASCODE', 'CASCODE'), Mos('MP2', P6, 1.0, 0.55, 'F2', 'F1', 'CASCODE', 'CASCODE'),
          Mos('CF1', P6, z['cfly'], z['cfly'], 'F1', 'CKA', 'F1', 'F1'), Mos('CF2', P6, z['cfly'], z['cfly'], 'F2', 'CKB', 'F2', 'F2')]
    # replica shunt / clamp, output reservoir, select switch, level shifter (6 V)
    d += [Mos('MR', P6, z['wr'], z['lr'], 'VDD', 'VDD', 'CASCODE', 'CASCODE', m=z['nr']),
          Mos('CO', N6, z['cout'], z['cout'], 'VSS', 'CASCODE', 'VSS', 'VSS', m=z['ncout']),
          Mos('MS', P6, z['ws'], 0.55, 'VDD', 'SG', 'CASCODE', 'CASCODE', m=z['ns']),
          Mos('ML1', N6, 1.0, 0.7, 'SG', 'ENB', 'VSS', 'VSS'), Mos('ML2', N6, 1.0, 0.7, 'SGB', 'EN', 'VSS', 'VSS'),
          Mos('MLP1', P6, 0.5, 0.55, 'SG', 'SGB', 'CASCODE', 'CASCODE'), Mos('MLP2', P6, 0.5, 0.55, 'SGB', 'SG', 'CASCODE', 'CASCODE')]
    return d


def circuit(z=SIZE):
    d = devices(z)
    names = [x.name for x in d]
    n3 = [x.name for x in d if x.model == N3]
    p3 = [x.name for x in d if x.model == P3]
    rows = [['CO'], ['MN1', 'MN2', 'ML1', 'ML2'], n3, p3, ['MP1', 'MP2', 'MLP1', 'MLP2', 'MS', 'MR'], ['CF1'], ['CF2']]
    assert sorted(sum(rows, [])) == sorted(names)
    c = ck.Circuit(NAME, PORTS, d, rows=rows, wide_nets={'VDD': 1.8, 'VSS': 1.8, 'CASCODE': 1.0})
    c.device_gap = 1.2
    c.notes = ['wtx8_casbias (wtx8_casbias.py): CASCODE pump + replica shunt + VDD select']
    return c


def netlist():
    return circuit().spice(include_macros=False)


def layout(work=WORK):
    import flow
    c = circuit()
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch = netlist()
    lay = ck.Layout(c, work).build()
    lay.write()
    (work / f'{NAME}.lvs_sch.spice').write_text(lay.lvs_reference(sch))
    res = ck.lvs(work, f'{NAME}.lvs.spice', NAME, f'{NAME}.lvs_sch.spice', NAME)
    gx = flow.export_gds(work, c)
    info = dict(lay.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx)
    (work / 'layout-info.json').write_text(json.dumps(info, indent=1, default=str) + '\n')
    return info


if __name__ == '__main__':
    if sys.argv[1:2] == ['layout']:
        i = layout()
        print(json.dumps({k: i.get(k) for k in ('drc_count', 'lvs', 'lvs_unique', 'bbox_um', 'area_um2')}, default=str))
    else:
        out = FAST / f'{NAME}.spice'
        out.write_text('* generated by wtx8_casbias.py (schematic; not published)\n' + netlist())
        print(out)
