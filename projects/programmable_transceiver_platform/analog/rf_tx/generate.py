"""Generate layout, DRC, extraction and LVS for one rf_tx block.

Usage: python3 generate.py <block> [--scratch DIR] [--publish DIR]
Raw Magic/Netgen work goes to scratch; compact outputs are copied to generated/.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import circuits
import layoutlib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


import os
RFD_DIODE_TAILS = os.environ.get('RFD_DIODE_TAILS', '1') == '1'   # RFT-07: reference in the tail row (default)


# rfdriver south pins, LEF frame (unflipped, origin at the drawn lower-left): placed FN with its die west edge at x 462, so
# die x = 462 + W - local x; the floorplan's trunk lane needs VDD at die x ~680-740 and VSS at ~745-770 (i13: W = drawn width)
RFD_PINS = {'VDD': (284.85, 344.85), 'VSS': (254.85, 279.85)}      # i13: W 562.85 -> die VDD 680-740, VSS 745-770


def _rows_rfdriver(c):
    names = [d.name for d in c.devices]
    rf = ['A1_P', 'A1_N', 'R1_p', 'R1_n', 'A2_P', 'A2_N', 'R2_p', 'R2_n', 'A3_P', 'A3_N', 'R3_p', 'R3_n',
          'RATBP_p', 'RATBP_n',
          'SF_p', 'SF_n', 'O_P', 'O_N', 'CAS_P', 'CAS_N']
    tails = ['T1', 'T2', 'T3', 'TS_p', 'TS_n', 'TO0', 'TO1', 'TO2', 'TO3', 'BCAP']
    if RFD_DIODE_TAILS:      # RFT-07: the bias reference sits in the tail row, on the tails' own VSS lane (mirror sees no IR offset)
        tails = ['T1', 'T2', 'T3', 'TS_p', 'TS_n', 'TO0', 'TO1', 'DIODE', 'RK', 'BSW', 'BPD', 'TO2', 'TO3', 'BCAP']
    load = ['HDR'] + [f'RO_{l}{i}' for l in 'pn' for i in range(circuits.DRV['ro_par'])] + ['CLP_p', 'CLP_n',
                                                                                          'RATBC_p', 'RATBC_n',
                                                                                          'DUM_P', 'DUM_N', 'CDC_P', 'CDC_N']
    sfh = ['SFH_a', 'SFH_b']        # SF drain header halves: the tallest logic row has the spare width
    used = set(rf + tails + load + sfh)
    rest = [n for n in names if n not in used]
    # RFT-01/D2: the pad-side bypass halves sit in the pad-load row (away from the pre-amps: pad->p1/p1b coupling
    # was 2-3 fF/leg and gave a negative output conductance); the in-side halves and the bm shunts in logic rows.
    byp = ('BYPA_p', 'BYPA_n', 'BYPB_p', 'BYPB_n', 'BSH_p', 'BSH_n')
    tb = ['BYPB_p', 'BSH_p', 'BYPB_n', 'BSH_n']
    rest = [n for n in rest if n not in tb] + [n for n in tb if n in rest]    # split as in scratch/rf-tx-d2 T4g8
    half = len(rest) // 2
    r3, r4 = [n for n in rest[:half] if n not in byp], [n for n in rest[half:] if n not in byp]
    rows = [rf, tails, ['BYPA_p'] + load + ['BYPA_n'], ['BSH_p', 'BYPB_p'] + r3, r4 + sfh + ['BYPB_n', 'BSH_n']]
    if os.environ.get('RFD_TAILS_BOTTOM', '1') == '1':    # RFT-07: the tail row (60 mA of VSS) next to the bottom supply bars
        rows = [rf, ['BYPA_p'] + load + ['BYPA_n'], ['BSH_p', 'BYPB_p'] + r3, r4 + sfh + ['BYPB_n', 'BSH_n'], tails]
    return [[n for n in r if n in names] for r in rows]


def _rows_txmix(c):
    names = [d.name for d in c.devices]
    core = ['QA', 'QB', 'QC', 'QD', 'GM_p', 'GM_n', 'RDEG', 'SATSW', 'SWB_p', 'SWD_p', 'SWB_n', 'SWD_n']
    tails = ['TAIL_p', 'TAIL_n', 'DIODE', 'BSW', 'BPD', 'CLG_p', 'CLG_n', 'RATB_B', 'RATB_T']
    rest = [n for n in names if n not in core + tails]
    return [core, tails, rest]


# LO feedthrough control: LO and mixer-output trunks at opposite ends of the bank,
# output lanes nearest the devices, then the VSS lane as a shield, LO lanes deepest.
MIX_ORDER = dict(trunk_order=['lo_p', 'lo_n', '*', 'out_p', 'out_n'],
                 lane_order=['out_p', 'out_n', 'VSS', 'd_p', 'd_n', 'src_p', 'src_n', 'lo_p', 'lo_n'])

def _rows_txsum(c):
    return [['RI_p', 'RQ_p', 'RL_p', 'RL_n', 'RQ_n', 'RI_n'],
            ['HDR', 'CL_p', 'CL_n', 'RATB_p', 'RATB_n', 'IEN_N', 'IEN_P']]


LAYOUT = {
    'txmix_i': dict(wide={'VDD': 1.0, 'VSS': 1.0, 'out_p': 0.6, 'out_n': 0.6}, rows=_rows_txmix, **MIX_ORDER),
    'txmix_q': dict(wide={'VDD': 1.0, 'VSS': 1.0, 'out_p': 0.6, 'out_n': 0.6}, rows=_rows_txmix, **MIX_ORDER),
    'txsum': dict(wide={'VDD': 1.0, 'VSS': 1.0, 'hsum': 1.0}, rows=_rows_txsum,
                  trunk_order=['i_p', 'i_n', 'q_p', 'q_n', '*', 'out_p', 'out_n']),
    # rfdriver power / R rework (RFT-07, 2026-11-28; candidate i11 of rfdriver_iter.py): edge-fed supply mesh (5 x 6 um Metal5
    # straps per supply, full-width bottom bars: VDD Metal5 4 um edge-flush, VSS Metal4 8 um under it), source/drain risers on
    # every column of the high-current nets (multi_escape), 3 um escapes on the RF / supply nets, Kelvin-sensed bias reference
    # in the tail row (circuits.DRV kelvin_ref) and the tail row next to the supply bars (_rows_rfdriver). Pins (LEF frame,
    # unflipped): VDD label at x 197.8-257.8 on the Metal5 bar, VSS label at x 167.8-192.8 on the Metal4 bar (floorplan spec).
    'rfdriver': dict(wide=dict({n: 0.8 for n in circuits.rfdriver().nets()},
                               **{'VDD': 3.0, 'VSS': 4.0, 'pad_p': 3.0, 'pad_n': 3.0, 'hdrv': 2.0, 'to': 3.0, 'cp': 3.0, 'cn': 3.0,
                                  't1': 1.0, 't2': 1.0, 't3': 1.0, 'p3_p': 2.0, 'p3_n': 2.0, 'vcp': 1.0, 'vcn': 1.0, 'sfd': 1.0}),
                     lane_width={'VDD': 1.5, 'VSS': 4.0, 'pad_p': 2.0, 'pad_n': 2.0, 'to': 2.0, 'cp': 2.0, 'cn': 2.0, 'hdrv': 1.2,
                                 'p3_p': 2.0, 'p3_n': 2.0},
                     multi_escape=dict({n: 2 for n in circuits.rfdriver().nets()},
                                       **{n: 1 for n in ('VSS', 'VDD', 'to', 'cp', 'cn', 'pad_p', 'pad_n', 'hdrv', 'p3_p', 'p3_n')}),
                     rows=_rows_rfdriver, inline_trunks=True, gap=0.8,
                     supply=dict(gap=1.0, stack=True,
                                 nets={'VDD': dict(straps=[0.05, 0.27, 0.49, 0.71, 0.93], w=6.0, bar=('metal5', 6.0), pin=('metal5', *RFD_PINS['VDD'])),
                                       'VSS': dict(straps=[0.085, 0.16, 0.305, 0.38, 0.525, 0.60, 0.745, 0.82, 0.965], w=6.0, bar=('metal4', 14.0),
                                                   pin=('metal4', *RFD_PINS['VSS']))})),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate(block, scratch, publish):
    c = circuits.BLOCKS[block]()
    work = Path(scratch) / block
    if work.exists():
        shutil.rmtree(work)
    opts = dict(LAYOUT[block])
    rows = opts.pop('rows')
    rep = layoutlib.build(c, work, rows=rows(c) if rows else None, **opts)
    src = work / 'src.spice'
    sch = c.spice()
    ant = layoutlib.ad.spice_lines(rep.get('antenna_diodes', []))   # LVS reference + antenna diodes
    if ant:
        k = sch.rstrip().rfind('.ends')
        sch = sch[:k] + '\n'.join(ant) + '\n' + sch[k:]
    src.write_text(sch)
    layoutlib.docker_netgen(work, f'{c.name}.lvs.spice', c.name, 'src.spice', c.name, 'lvs.txt')
    lvs_txt = (work / 'lvs.txt').read_text() if (work / 'lvs.txt').exists() else ''
    final = [l for l in lvs_txt.splitlines() if l.startswith('Final result')]
    unique = bool(final) and 'match uniquely' in final[-1]
    name_eq = name_equivalent(src, work / f'{c.name}.lvs.spice', c.name)
    pub = Path(publish)
    pub.mkdir(parents=True, exist_ok=True)
    (HERE / f'{block}.spice').write_text(c.spice())
    for suffix in ('.gds', '.mag', '.ext.spice'):
        shutil.copy(work / f'{c.name}{suffix}', pub / f'{block}{suffix}')
    shutil.copy(work / 'lvs.txt', pub / f'{block}-lvs.txt')
    shutil.copy(work / 'drc-details.txt', pub / f'{block}-drc.txt')
    bb = rep['bbox_um']
    report = dict(block=block, cell=c.name, image=layoutlib.DIGITAL_IMAGE,
                  image_id=layoutlib.image_id(layoutlib.DIGITAL_IMAGE),
                  pdk=f'{layoutlib.PDK} (open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7)',
                  drc_errors=int(rep['drc_count']), lvs_unique_match=unique,
                  lvs_final=final[-1] if final else 'netgen produced no result',
                  # netgen sees the PDK devices as black-box placeholders, so parallel fingers merge without
                  # W: the four binary tail slices (12/24/48/96 fingers) become indistinguishable and the
                  # automorphism can land on a g0..g3 pin permutation. The layout keeps every net label, so a
                  # device-by-device comparison by net name (model, gate, {d,s}, bulk, W, L) is exact.
                  lvs_name_equivalent=name_eq,
                  bbox_um=bb, width_um=round(bb['x1'] - bb['x0'], 2), height_um=round(bb['y1'] - bb['y0'], 2),
                  area_um2=rep['area_um2'],
                  area_ceiling_um2=circuits_area_ceiling(block),
                  rows=rep['rows'], trunked_nets=rep['trunked_nets'], circuit=c.summary(),
                  supply_straps_um=rep.get('supply_straps_um'), supply_bars_um=rep.get('supply_bars_um'), supply_pins_um=rep.get('supply_pins_um'),
                  hashes={f'{block}.spice': sha(HERE / f'{block}.spice'), 'circuits.py': sha(HERE / 'circuits.py'),
                          'layoutlib.py': sha(HERE / 'layoutlib.py'), 'generate.py': sha(HERE / 'generate.py'),
                          f'{block}.gds': sha(pub / f'{block}.gds'), f'{block}.ext.spice': sha(pub / f'{block}.ext.spice')},
                  limitations=['Extraction is capacitance-only (ext2spice cthresh 0); wire and via resistance are not extracted.',
                               'Single-block DRC with the Magic gf180mcuD deck; no KLayout signoff deck, antenna or density run.'])
    (pub / f'{block}-layout.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def name_equivalent(src, lay, top):
    """True when both netlists hold the identical multiset of (model, gate, {d,s}, bulk, w, l) by net name."""
    import collections
    def devs(fn):
        t = Path(fn).read_text().replace('\n+', ' ')
        inside, out = False, collections.Counter()
        for l in t.splitlines():
            f = l.split()
            if not f:
                continue
            if f[0].lower() == '.subckt' and f[1] == top:
                inside = True
                continue
            if f[0].lower() == '.ends':
                inside = False
            if inside and f[0][0] in 'Xx':
                pos = [x for x in f[1:] if '=' not in x]
                kv = dict(x.split('=', 1) for x in f[1:] if '=' in x)
                model, pins = pos[-1], pos[:-1]
                if model.startswith(('nfet', 'pfet')) and len(pins) == 4:
                    key = (model, pins[1], tuple(sorted((pins[0], pins[2]))), pins[3], kv.get('w'), kv.get('l'))
                else:
                    key = (model, tuple(sorted(pins[:2])), tuple(pins[2:]), kv.get('w'), kv.get('l'))
                out[key] += 1
        return out
    a, b = devs(src), devs(lay)
    return bool(a) and a == b


def circuits_area_ceiling(block):
    arch = json.loads((HERE.parents[1] / 'spec/analog-architecture.json').read_text())
    return arch['blocks'][block]['resource_allocation']['area_ceiling_um2']


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('block', choices=sorted(circuits.BLOCKS))
    ap.add_argument('--scratch', default=str(REPO / 'scratch/rf_tx/layout'))
    ap.add_argument('--publish', default=str(HERE / 'generated'))
    a = ap.parse_args()
    r = generate(a.block, a.scratch, a.publish)
    print(json.dumps({k: r[k] for k in ('block', 'drc_errors', 'lvs_unique_match', 'area_um2', 'area_ceiling_um2',
                                        'width_um', 'height_um')}))
