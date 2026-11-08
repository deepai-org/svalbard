"""Extracted-netlist ('clean' test) simulations of the generated layouts.

Uses Magic C-coupled extraction (sak-pex.sh -m 2) of each cell, renamed to the
schematic subckt name so the schematic testbenches run unchanged. Function is
checked at the operating-envelope points (sim.F_POINTS); one safety case per
cell is repeated on the extracted netlist.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design  # noqa: E402
import sim  # noqa: E402

ISW_PORTS = ['VDD', 'VSS', 'VISL', 'EN', 'ISO', 'PG']
ATB_PORTS = {'atb_leaf_s': ['NODE', 'BUS', 'SEL', 'VDD', 'VSS'], 'atb_leaf_f': ['NODE', 'BUS', 'SEL', 'VDD', 'VSS'],
             'atb_grp': ['NODE', 'BUS', 'SEL', 'VDD', 'VSS'], 'atb_pad': ['PAD', 'BUS', 'SEL', 'VDD', 'VSS']}


def _c(v):
    return {k: x for k, x in v.items() if not k.startswith('_')}


def campaign(pexdir, schem, workers):
    sim.WORK = Path('/work/sims_pex')
    alloc, sizes = schem['allocation'], schem['sizes']
    out = {'isw': {}, 'atb': {}, 'pex_sha256': {}}
    for isl in alloc:
        cell = f'isw_{isl}'
        path = Path(pexdir) / cell / f'{cell}.pex.spice'
        if not path.exists():
            out['isw'][isl] = {'error': 'no extracted netlist'}
            continue
        out['pex_sha256'][cell] = hashlib.sha256(path.read_bytes()).hexdigest()
        sim.OVERRIDE.clear()
        sim.OVERRIDE['isw'] = sim.load_pex(path, 'isw', ISW_PORTS)
        nf = sizes[isl]['fingers']
        a = alloc[isl]
        jobs = [sim.isw_drop_job(isl, nf, c, t, v, a['design_current_ma']) for c, t, v in sim.F_POINTS]
        jobs += [sim.isw_leak_job(isl, nf, c, t, 3.35) for c in ('tt', 'ss', 'ff') for t in (22, 32)]
        jobs += [sim.isw_tran_job(isl, nf, c, t, v, a['peak_allocation_ma'], a['island_decap_f'], 130.0)
                 for c, t, v in [('tt', 27, 3.3), ('ss', 32, 3.3), ('ff', 22, 3.3)]]
        jobs += [sim.isw_reverse_job(isl, nf, 'tt', 27, vdd, vi, 'bodyswitch') for vdd, vi in [(0.0, 3.63), (3.3, 3.63)]]
        res = sim.run_all(jobs, workers)
        drops = {k: v.get('drop') for k, v in res.items() if k.startswith('drop_')}
        out['isw'][isl] = {
            'design_current_ma': a['design_current_ma'],
            'functional_drop_max_v': max(x for x in drops.values() if x is not None) if any(x is not None for x in drops.values()) else None,
            'functional_cases': len(drops), 'functional_converged': sum(x is not None for x in drops.values()),
            'drop_tt_27_3v3_v': drops.get(f'drop_{isl}_tt_27_3.3'),
            'drop_pass': all(x is not None and x <= design.DROP_TARGET_V + 1e-6 for x in drops.values()),
            'pg_iso_ok': all(res[k].get('pg', 0) > 3.0 and res[k].get('iso', 9) < 0.1 for k in drops),
            'leak_max_3v35_22to32c_a': max(res[k]['ileak'] for k in res if k.startswith('leak_')),
            'transient': {k: _c(v) for k, v in res.items() if k.startswith('tran_')},
            'reverse': {k: _c(v) for k, v in res.items() if k.startswith('rev_')},
        }
    sim.OVERRIDE.clear()
    # Record the sak-pex (ext2spice lvs mode) off capacitance for comparison,
    # then use the default-mode extraction (pexd) for all ATB results.
    lvsmode = {}
    for cell, ports in ATB_PORTS.items():
        path = Path(pexdir) / cell / f'{cell}.pex.spice'
        if path.exists() and cell != 'atb_pad':
            sim.OVERRIDE.clear()
            sim.OVERRIDE[cell] = sim.load_pex(path, cell, ports)
            r = sim.run_all([sim.atb_offc_job(cell, 'tt', 22, 1.65, 0.0)], 1)
            lvsmode[cell] = next(iter(r.values())).get('cnode')
    out['atb_lvsmode_off_c_tt22_mid_f'] = lvsmode
    sim.OVERRIDE.clear()
    pexd = Path(pexdir).parent / 'pexd'
    for cell, ports in ATB_PORTS.items():
        path = pexd / cell / f'{cell}.pex.spice'
        if path.exists():
            out['pex_sha256'][cell] = hashlib.sha256(path.read_bytes()).hexdigest()
            sim.OVERRIDE[cell] = sim.load_pex(path, cell, ports)
    atb_ex = [c for c in ATB_PORTS if c in sim.OVERRIDE]
    jobs = []
    for cell in atb_ex:
        for c, t, v in sim.F_POINTS:
            for vs in [x * 0.15 for x in range(int(round(v / 0.15)) + 1)]:
                jobs.append(sim.atb_ron_job(cell, c, t, v, round(min(vs, v), 3)))
            jobs.append(sim.atb_bbm_job(cell, c, t, v))
    for cell in [c for c in atb_ex if c != 'atb_pad']:
        for c in ('tt', 'ss', 'ff'):
            for t in (22, 32):
                for vn in (0.0, 1.65, 3.35):
                    for vb in (0.0, 3.35):
                        jobs.append(sim.atb_offc_job(cell, c, t, vn, vb))
        jobs.append(sim.atb_iso_job(cell, 'tt', 27))
    if 'atb_pad' in atb_ex:
        jobs += [sim.atb_pad_unpowered_job('tt', t, vdd, vp, 0.0) for t in (27, 85)
                 for vdd, vp in [(0.0, 3.63), (3.3, 3.63), (3.3, -0.3)]]
    if all(c in atb_ex for c in ATB_PORTS):
        jobs += [sim.atb_forcesense_job('tt', 27), sim.atb_settle_job('tt', 27)]
    res = sim.run_all(jobs, workers)
    for cell in atb_ex:
        ron = {k: v['ron'] for k, v in res.items() if k.startswith(f'ron_{cell}_') and 'ron' in v}
        nr = sum(1 for k in res if k.startswith(f'ron_{cell}_'))
        bbm = {k: v for k, v in res.items() if k.startswith(f'bbm_{cell}_')}
        gaps = [v.get('gap_ab') for v in bbm.values()]
        igaps = [v.get('gap_a_internal') for v in bbm.values()] + [v.get('gap_b_internal') for v in bbm.values()]
        entry = {'ron_functional_max_ohm': max(ron.values()) if ron else None, 'ron_cases': nr,
                 'ron_converged': len(ron),
                 'ron_tt_27_3v3_max_ohm': max((v for k, v in ron.items() if '_tt_27_3.3_' in k), default=None),
                 'bbm_cases': len(bbm),
                 'bbm_min_gap_between_cells_s': min(gaps) if gaps and all(g is not None for g in gaps) else None,
                 'bbm_min_internal_gap_s': min(igaps) if igaps and all(g is not None for g in igaps) else None}
        offc = {k: v for k, v in res.items() if k.startswith(f'offc_{cell}_')}
        if offc:
            entry.update({'off_c_max_f': max(v['cnode'] for v in offc.values() if 'cnode' in v),
                          'off_c_min_f': min(v['cnode'] for v in offc.values() if 'cnode' in v),
                          'off_c_tt_22_mid_f': offc.get(f'offc_{cell}_tt_22_1.65_0.0', {}).get('cnode'),
                          'off_leak_abs_max_22to32c_a': max(abs(v['ileak']) for v in offc.values() if 'ileak' in v),
                          'off_cases': len(offc)})
        iso = res.get(f'iso_{cell}_tt_27')
        if iso:
            entry['isolation_db_into_10k_node_tt27'] = _c(iso)
        out['atb'][cell] = entry
    out['atb']['pad_overvoltage'] = {k: _c(v) for k, v in res.items() if k.startswith('padov_')}
    out['atb']['force_sense'] = {k: _c(v) for k, v in res.items() if k.startswith('fs_')}
    out['atb']['sense_settling'] = {k: _c(v) for k, v in res.items() if k.startswith('settle_')}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--schematic', default='/work/schematic-result.json')
    ap.add_argument('--pex', default='/work/pex')
    ap.add_argument('--out', default='/work/extracted-result.json')
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    schem = json.loads(Path(a.schematic).read_text())
    res = campaign(a.pex, schem, a.workers)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
