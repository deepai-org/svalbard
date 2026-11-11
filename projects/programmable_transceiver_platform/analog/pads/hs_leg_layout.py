#!/usr/bin/env python3
"""PD21 low-C HS pad: per-leg front-end block `pt_hs_leg` (convkit rows, Magic DRC/LVS, KLayout via flow.export_gds).

Ports PAD RX VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0..3 VDD VSS. One leg (the composition mirrors it for N):
  row0  25 x nfet_06v0 TU_i -> TERM_VCM: 10 base units 20/0.7 (gate TERM_ENABLE), 15 trim units 12/0.7
        (gates TERM_TRIMk, 1/2/4/8 units)
  row1  25 x ppolyf_u PAD -> TU_i: base 2 x 3.05 um, trim 2 x 2.0 um
  row2  AC coupling MIM 2 x 35 x 35 um (cap_mim_2f0_m4m5, ~4.9 pF): bottom plate = PAD, top = RX
  row3  RX bias ppolyf_u_1k 1 x 40 um (~40 kohm, HPF ~0.8 MHz) RX -> VBIAS; RX secondary clamps (drain diodes of
        grounded-gate 6 V devices): pfet_06v0 4/0.55 to VDD, nfet_06v0 4/0.7 to VSS
Every pad-reachable node is on 6 V devices (TU follows the pad during HBM); the RX side is DC-isolated by the MIM.
    python3 hs_leg_layout.py <work dir>
"""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CONV = HERE.parent / 'converters'
sys.path.insert(0, str(CONV / 'lib')); sys.path.insert(0, str(CONV))
import convkit as ck  # noqa: E402
from convkit import Mos, Res, Cap, Circuit  # noqa: E402

N_BASE = 10
GATES = ['TERM_ENABLE'] * N_BASE + [f'TERM_TRIM{k}' for k in range(4) for _ in range(1 << k)]

_mag = ck.mag_rects
def _mag_mv(path):
    r, props = _mag(path)
    for a, b in (('mvndiffc', 'ndiffc'), ('mvpdiffc', 'pdiffc')):
        if a in r and b not in r:
            r[b] = r[a]
    return r, props
ck.mag_rects = _mag_mv
_gen = ck.gencell_cmd
def _gen6(key):
    if key[0] == 'mos' and key[1] in ('nfet_06v0', 'pfet_06v0'):
        return (f'magic::gencell_makecell gf180mcu::{key[1]} w {key[2]} l {key[3]} nf 1 guard 1 topc 0 botc 1 '
                'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8')
    if key[0] == 'resu':
        return f'magic::gencell_makecell gf180mcu::ppolyf_u w {key[1]} l {key[2]} guard 1 full_metal 1'
    return _gen(key)
ck.gencell_cmd = _gen6
_pg = ck.pcell_geometry
def _pg_u(key, path):
    return _pg(('res',) + tuple(key[1:]) if key[0] == 'resu' else key, path)
ck.pcell_geometry = _pg_u


class ResU(Res):
    """Unsalicided low-R p-poly (ppolyf_u) unit, same pins as convkit Res."""
    def spice(self):
        return [f'X{self.name}_{i} {self.a} {self.b} {self.sub} ppolyf_u r_width={self.w}u r_length={self.l}u' for i in range(self.m)]
    def key(self):
        return ('resu', self.w, self.l)


def circuit(name='pt_hs_leg'):
    d = []
    for i, g in enumerate(GATES):
        # base units (always on when terminated): 20 um switch, 2 x 3.05 um poly; trim units (often off): 12 um
        # switch (off-state C 12.8 vs 21 fF) with 2 x 2.0 um poly, same unit resistance within the corner spread
        ws, lu = (20., 3.05) if g == 'TERM_ENABLE' else (12., 2.0)
        d.append(Mos(f'S{i}', 'nfet_06v0', ws, .7, f'TU{i}', g, 'TERM_VCM', 'VSS'))
        d.append(ResU(f'R{i}', 2., lu, 'PAD', f'TU{i}', 'VSS'))
    d.append(Cap('CAC', 35., 35., 'RX', 'PAD', m=2))
    d.append(Res('RB', 1., 40., 'VBIAS', 'RX', 'VSS'))
    d.append(Mos('CLH', 'pfet_06v0', 4., .55, 'RX', 'VDD', 'VDD', 'VDD', flip=True))
    d.append(Mos('CLL', 'nfet_06v0', 4., .7, 'RX', 'VSS', 'VSS', 'VSS', flip=True))
    # Protection-rail precharge (C of the pad->rail diodes at low CM): drain diode VDD (p+) -> RAILPRE (n-well),
    # routed to the shell's ATB_ESD_RAIL tap (480 kohm to the rail). Reverse-biased when unpowered (no backfeed).
    d.append(Mos('PRE', 'pfet_06v0', 4., .55, 'VDD', 'RAILPRE', 'RAILPRE', 'RAILPRE'))
    rows = [[f'S{i}' for i in range(len(GATES))], [f'R{i}' for i in range(len(GATES))], ['CAC'], ['RB', 'CLH', 'CLL', 'PRE']]
    ports = ['PAD', 'RX', 'VBIAS', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VDD', 'VSS', 'RAILPRE']
    c = Circuit(name, ports, d, rows=rows, wide_nets={'PAD': 2.0, 'VSS': 2.0, 'TERM_VCM': 1.0, 'RX': 1.0})
    c.notes = ['pt_hs_leg (PD21): termination units + AC-coupling MIM + RX bias/clamps, one leg']
    return c


def layout(work):
    import flow
    c = circuit()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch = c.spice(include_macros=False)
    (work / f'{c.name}.sch.spice').write_text(sch)
    L = ck.Layout(c, work).build()
    L.write()
    (work / f'{c.name}.lvs_sch.spice').write_text(L.lvs_reference(sch))
    res = ck.lvs(work, f'{c.name}.lvs.spice', c.name, f'{c.name}.lvs_sch.spice', c.name)
    gx = flow.export_gds(work, c)
    info = dict(L.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx)
    (work / 'layout-info.json').write_text(json.dumps(info, indent=2, default=str) + '\n')
    print(json.dumps({k: info.get(k) for k in ('drc_count', 'lvs', 'lvs_unique')}, default=str), gx.get('klayout_drc'))
    return info


if __name__ == '__main__':
    layout(Path(sys.argv[1]).resolve())
