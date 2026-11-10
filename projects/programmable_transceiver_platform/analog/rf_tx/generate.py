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


def _rows_rfdriver(c):
    names = [d.name for d in c.devices]
    rf = ['BYP_p', 'A1_P', 'A1_N', 'BYP_n', 'R1_p', 'R1_n', 'A2_P', 'A2_N', 'R2_p', 'R2_n', 'A3_P', 'A3_N', 'R3_p', 'R3_n',
          'RATBP_p', 'RATBP_n',
          'SF_p', 'SF_n', 'O_P', 'O_N']
    tails = ['T1', 'T2', 'T3', 'TS_p', 'TS_n', 'TO0', 'TO1', 'TO2', 'TO3', 'BCAP']
    load = ['HDR'] + [f'RO_{l}{i}' for l in 'pn' for i in range(circuits.DRV['ro_par'])] + ['CLP_p', 'CLP_n',
                                                                                          'RATBC_p', 'RATBC_n']
    used = set(rf + tails + load)
    rest = [n for n in names if n not in used]
    half = len(rest) // 2
    rows = [rf, tails, load, rest[:half], rest[half:]]
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
    'rfdriver': dict(wide={'VDD': 2.0, 'VSS': 2.0, 'pad_p': 2.0, 'pad_n': 2.0, 'hdrv': 2.0, 'to': 2.0,
                           't1': 0.8, 't2': 0.8, 'p3_p': 0.8, 'p3_n': 0.8},
                     rows=_rows_rfdriver),
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
                  bbox_um=bb, width_um=round(bb['x1'] - bb['x0'], 2), height_um=round(bb['y1'] - bb['y0'], 2),
                  area_um2=rep['area_um2'],
                  area_ceiling_um2=circuits_area_ceiling(block),
                  rows=rep['rows'], trunked_nets=rep['trunked_nets'], circuit=c.summary(),
                  hashes={f'{block}.spice': sha(HERE / f'{block}.spice'), 'circuits.py': sha(HERE / 'circuits.py'),
                          'layoutlib.py': sha(HERE / 'layoutlib.py'), 'generate.py': sha(HERE / 'generate.py'),
                          f'{block}.gds': sha(pub / f'{block}.gds'), f'{block}.ext.spice': sha(pub / f'{block}.ext.spice')},
                  limitations=['Extraction is capacitance-only (ext2spice cthresh 0); wire and via resistance are not extracted.',
                               'Single-block DRC with the Magic gf180mcuD deck; no KLayout signoff deck, antenna or density run.'])
    (pub / f'{block}-layout.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


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
