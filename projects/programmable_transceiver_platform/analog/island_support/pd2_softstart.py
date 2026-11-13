"""PD2 (2026-11-13): soft-start / inrush of the re-partitioned islands on the EXISTING verified switch masters.

The island re-partition (spec/power-delivery.md section 2, spec/budgets/power_budget.py ISLAND_SWITCH) instantiates the
five verified masters under new island loads and island capacitances. Static drop needs no new run: every island's
worst current is at or below its master's design current, at which the full-RC drop is already <= 20 mV at all 13
functional points (evidence.json). This script reruns the turn-on transient on the EXTRACTED masters at the new
(load, island C) points, with island C two-sided (the planned value and 5x: MIM decap on an island rail must not break
the soft start), plus one group case: the four RF-side islands enabled by one EN edge on the common-ring PDN.

Runs inside the pinned iic-osic-tools image (see pd2_softstart.sh). Usage: pd2_softstart.py PEXDIR SCHEMATIC_JSON OUT
"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import design, sim  # noqa: E402

PORTS = ['VDD', 'VSS', 'VISL', 'EN', 'ISO', 'PG']
# island: (master, worst island current mA (power_budget.py pd2_reconcile), island C in F (model value), )
ISLANDS = {'wired_cap': ('wired', 67.6, 100e-12), 'wired_rx': ('debug', 28.7, 60e-12), 'lod': ('wired', 66.6, 150e-12), 'wired_tx': ('debug', 37.5, 50e-12),
           'rf_rx': ('rf', 38.2, 120e-12), 'rf_tx': ('debug', 26.3, 80e-12), 'pll': ('debug', 26.4, 150e-12),
           'lo': ('conv', 27.5, 100e-12), 'conv': ('conv', 18.7, 250e-12)}
CORNERS = [('tt', 27, 3.3), ('ss', 32, 3.3), ('ff', 22, 3.3)]
BG_MA = 130.0


def group_job(S, corner, temp, vs, members):
    """Several switches (schematic masters) on one EN edge and one common-ring PDN."""
    t = sim.header(corner, temp)
    for isl in members:
        m = ISLANDS[isl][0]
        t += design.isw_netlist(f'isw_{m}', S['sizes'][m]['fingers']) if f'.subckt isw_{m} ' not in t else ''
    t += sim.pdn(BG_MA).replace('{VS}', str(vs))
    t += f'VEN EN 0 PWL(0 0 20u 0 20.01u {vs} 60u {vs} 60.01u 0)\n'
    for isl in members:
        m, ma, c = ISLANDS[isl]
        t += (f'XI_{isl} VDD 0 VS_{isl} EN ISO_{isl} PG_{isl} isw_{m}\nVM_{isl} VS_{isl} V_{isl} 0\nCI_{isl} V_{isl} 0 {c}\n'
              f'RL_{isl} V_{isl} 0 {3.3/(ma*1e-3):.4g}\n')
    isum = '+'.join(f'i(vm_{isl})' for isl in members)
    t += ('.tran 20n 60u 0 20n\n.control\nrun\n'
          'meas tran vdd_pre find v(vdd) at=19u\nmeas tran vdd_min min v(vdd) from=20u to=59u\nmeas tran vdd_final find v(vdd) at=59u\n'
          f'let isum = {isum}\nmeas tran i_peak max isum from=20u to=59u\nmeas tran i_final find isum at=59u\n'
          + ''.join(f'meas tran pg_{isl} when v(pg_{isl})=1.5 rise=1\n' for isl in members) + '.endc\n.end\n')
    return (f'group_{"_".join(members)}_{corner}_{temp}', t)


def main():
    pexdir, schem, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
    workers = int(os.environ.get('WORKERS', '2'))
    sim.WORK = out.parent / 'sims_pd2'
    res = {'method': 'extracted (C-coupled PEX) masters; common-ring PDN of sim.pdn(); 130 mA background', 'islands': {}}
    only = [x for x in os.environ.get('ONLY', '').split(',') if x]      # rerun a subset and merge into an existing result
    if only and out.exists(): res = json.loads(out.read_text())
    for isl, (m, ma, c) in ISLANDS.items():
        if only and isl not in only: continue
        sim.OVERRIDE.clear()
        sim.OVERRIDE['isw'] = sim.load_pex(pexdir / f'isw_{m}' / f'isw_{m}.pex.spice', 'isw', PORTS)
        nf = schem['sizes'][m]['fingers']
        jobs = []
        for cc, tag in ((c, 'c1'), (5*c, 'c5')):
            for corner, t, v in (CORNERS if tag == 'c1' else CORNERS[:1]):     # 5x island C at tt only (box load)
                name, text = sim.isw_tran_job(isl, nf, corner, t, v, ma, cc, BG_MA, tag=tag, t_off=60e-6, t_stop=80e-6)
                jobs.append((name, text))
        r = sim.run_all(jobs, workers)
        cases = {}
        for k, v in r.items():
            ok = all(x in v for x in ('vdd_min', 'vdd_final', 'i_peak', 't_on', 't_10', 't_pg'))
            cases[k] = dict(v, ok=ok, ring_undershoot_v=(max(0.0, v['vdd_final']-v['vdd_min']) if ok else None),
                            rail_10_90_s=(v['t_on']-v['t_10'] if ok else None))
        good = [v for v in cases.values() if v['ok']]
        res['islands'][isl] = {
            'master': f'isw_{m}', 'load_ma': ma, 'island_c_f': [c, 5*c], 'cases': len(cases), 'converged': len(good),
            'ring_undershoot_max_v': max((v['ring_undershoot_v'] for v in good), default=None),
            'switch_current_peak_a': max((v['i_peak'] for v in good), default=None),
            'peak_over_load': max((v['i_peak']/(ma*1e-3*v['visl_final']/3.3) for v in good), default=None),
            'rail_10_90_s_range': [min((v['rail_10_90_s'] for v in good), default=None), max((v['rail_10_90_s'] for v in good), default=None)],
            'en_to_pg_s_max': max((v['t_pg']-20e-6 for v in good), default=None),
            'pass': len(good) == len(cases) and max(v['ring_undershoot_v'] for v in good) <= 0.005
                    and max(v['i_peak']/(ma*1e-3*v['visl_final']/3.3) for v in good) <= 1.10,
            'detail': cases}
        out.write_text(json.dumps(res, indent=1))
    sim.OVERRIDE.clear()
    jobs = [group_job(schem, c, t, v, ['rf_rx', 'rf_tx', 'lod', 'lo']) for c, t, v in CORNERS]
    jobs += [group_job(schem, 'tt', 27, 3.3, ['wired_rx', 'wired_cap', 'wired_tx'])]
    r = sim.run_all(jobs, workers)
    res['group'] = {k: dict(v, ring_undershoot_v=(max(0.0, v['vdd_final']-v['vdd_min']) if 'vdd_min' in v and 'vdd_final' in v else None),
                            peak_over_final=(v['i_peak']/v['i_final'] if 'i_peak' in v and v.get('i_final') else None)) for k, v in r.items()}
    # negative control: the same bench with an abrupt gate drive (no soft start) must break the criteria
    nm, tx = sim.isw_tran_job('negctl', schem['sizes']['wired']['fingers'], 'tt', 27, 3.3, 67.6, 100e-12, BG_MA, tag='abrupt',
                              ss_m=40, ss_l=0.28, t_off=60e-6, t_stop=80e-6)
    v = sim.run_all([(nm, tx)], 1)[nm]
    und = max(0.0, v['vdd_final']-v['vdd_min']) if 'vdd_min' in v and 'vdd_final' in v else None
    res['negative_control_abrupt_gate'] = dict(ring_undershoot_v=und, i_peak_a=v.get('i_peak'),
                                               fails_as_required=bool(und is not None and (und > 0.005 or v['i_peak'] > 1.10*67.6e-3)))
    res['criteria'] = 'ring dip below its settled value <= 5 mV; peak switch current <= 1.10 x the island load; every case converged'
    res['islands'] = {k: v for k, v in res['islands'].items() if k in ISLANDS}
    res['pass'] = all(v['pass'] for v in res['islands'].values()) and len(res['islands']) == len(ISLANDS) and all(
        v['ring_undershoot_v'] is not None and v['ring_undershoot_v'] <= 0.005 and v['peak_over_final'] <= 1.10 for v in res['group'].values()) and res['negative_control_abrupt_gate']['fails_as_required']
    out.write_text(json.dumps(res, indent=1))
    print('wrote', out, 'pass' if res['pass'] else 'FAIL')


if __name__ == '__main__':
    main()
