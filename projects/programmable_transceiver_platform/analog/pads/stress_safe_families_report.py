"""Collect the stress-safe family layouts, area fit and per-family runs into one report.

Reads only published files under generated/stress-safe-families/ plus the
simulation report given on the command line; writes families-report.json there.
"""
import argparse
import hashlib
import json
from pathlib import Path

PADS = Path(__file__).resolve().parent
G = PADS / 'generated/stress-safe-families'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--sims', type=Path, required=True)
    args = a.parse_args()
    sims = json.loads(args.sims.read_text())
    arch = json.loads((PADS.parents[1] / 'spec/analog-architecture.json').read_text())['blocks']
    ceiling = lambda b: arch[b]['resource_allocation']['area_ceiling_um2']
    rf = json.loads((G / 'rf-pair/pad-layout.json').read_text())
    esd = json.loads((G / 'single-leg/pad-layout.json').read_text())
    macro = json.loads((G / 'network-shunt/network-layout.json').read_text())
    layouts, area = {}, {}
    for block, d in (('refpad', 'reference'), ('txpad', 'wired-transmit'), ('wirepad', 'wired-receive-usb')):
        screen = json.loads((G / d / 'layout-screen.json').read_text())
        place = json.loads((G / d / 'placement-layout.json').read_text())
        layouts[block] = dict(dir=f'generated/stress-safe-families/{d}', drc_count=screen['drc_count'],
                              device_lvs_match=screen['device_lvs_match'], independent_device_graph_match=screen['independent_device_graph_match'],
                              device_count=screen['device_count'],
                              contains=['canonical family base', 'stress-safe macro: network + gate discharge + ATB tap + v2 shunt and straps'],
                              gds_check='Magic reads combined.gds (KLayout-written) for DRC, extraction, netgen LVS and the independent device audit',
                              gds_sha256=sha(G / d / 'combined.gds'))
        used = place['allocation_union_um2']
        area[block] = dict(allocation_um2=round(used), ceiling_um2=ceiling(block), headroom_um2=round(ceiling(block) - used),
                           fits=used <= ceiling(block))
    for block in ('rfpad', 'rftxpad'):
        used = rf['geometry']['allocation_union_um2']
        layouts[block] = dict(dir='generated/stress-safe-families/rf-pair', drc_count=rf['drc_count'], lvs=rf['device_graph_lvs_match'],
                              shared_with='rfpad and rftxpad use the same physical pair', gds_sha256=sha(G / 'rf-pair/pad.gds'),
                              note='pad-layout.json fits_assigned_area uses the stale 130,000 um2 ceiling copied from rf-receive-layout.json; checked here against spec/analog-architecture.json')
        area[block] = dict(allocation_um2=round(used), ceiling_um2=ceiling(block), headroom_um2=round(ceiling(block) - used), fits=used <= ceiling(block))
    net = macro
    res = [r for r in sims['results'] if 'error' not in r]
    errors = [r for r in sims['results'] if 'error' in r]
    safe, function = {}, {}
    for r in res:
        if 'case' in r:
            safe.setdefault(r['family'], []).append(r)
        else:
            function.setdefault(r['family'], []).append(r)
    summary = {}
    for fam in ('refpad', 'txpad', 'wirepad', 'rfpad'):
        sf = safe.get(fam, [])
        pulses = [r for r in sf if r['case'].startswith('pulse')]
        peer = [r for r in sf if r['case'] == 'peer']
        ramps = [r for r in sf if r['case'].startswith('ramp')]
        fn = function.get(fam, [])
        entry = dict(
            pulses=dict(runs=len(pulses), complete=all(r['complete'] for r in pulses),
                        op_fallback=any(r.get('op_fallback') for r in pulses),
                        max_pad_v=max((r['pad_p_range_v'][1] for r in pulses), default=None) and max(max(r['pad_p_range_v'][1], r['pad_n_range_v'][1]) for r in pulses),
                        min_pad_v=min((min(r['pad_p_range_v'][0], r['pad_n_range_v'][0]) for r in pulses), default=None),
                        rail_max_v=max((r['rail_max_v'] for r in pulses), default=None),
                        observed_mos=max((r['exposure']['observed_mos'] for r in pulses), default=0),
                        exceeding=sum(r['exposure']['exceeding'] for r in pulses),
                        all_within_6v0=all(r['pad_within_6v0_screen'] for r in pulses)),
            powered_peer=[dict(corner=f"{r['process']}/{r['temp_c']}C", pad_v=r['pad_p_range_v'][1], peer_current_a=r['peer_current_end_a'],
                               vdd_backfeed_peak_a=r['vdd_backfeed_peak_a'], atb_v=r['atb_range_v'][1], rail_v=r['rail_max_v'],
                               exceeding=r['exposure']['exceeding'], op_fallback=r.get('op_fallback')) for r in peer],
            ramps=[dict(case=r['case'], supply_current_end_a=r['supply_current_end_a'], max_pad_v=max(r['pad_p_range_v'][1], r['pad_n_range_v'][1]),
                        exceeding=r['exposure']['exceeding'], op_fallback=r.get('op_fallback')) for r in ramps])
        if fam == 'rfpad':
            entry['function'] = [dict(corner=f"{r['process']}/{r['temp_c']}C", bias_v=r['bias_v'], transfer_db=r['diff_transfer_db'],
                                      excess_loss_db=[round(x - r['ideal_50ohm_divider_db'], 4) for x in r['diff_transfer_db']]) for r in fn]
        else:
            base = next((r for r in fn if r['baseline']), None)
            new = [r for r in fn if not r['baseline']]
            entry['function'] = dict(baseline=base, runs=[dict(corner=f"{r['process']}/{r['temp_c']}C/{r['vdd_v']}V", complete=r['complete'],
                                     op_fallback=r['op_fallback'], final_diff_pp_v=r['final_diff_pp_v'],
                                     final_cm_v=(r['final_pad_p_mean_v'] + r['final_pad_n_mean_v']) / 2,
                                     rail_final_v=r.get('rail_final_v'), atb_final_v=r.get('atb_final_v')) for r in new])
        summary[fam] = entry
    out = dict(status='stress_safe_family_closure_attempt_not_ESD_qualified',
               network=dict(dir='generated/stress-safe-families/network-shunt', drc_count=net['drc_count'], lvs=net['device_graph_lvs_match'],
                            additions=net['additions'], ports=net['ports'], straps=net['straps'], wiring_resistance=net['wiring_resistance'],
                            allocation_regions_um=net['allocation_regions_um'],
                            canonical_geometry_unchanged='network part: KLayout comparison, no canonical shape removed; additions in x 62.8..135.3, y -2..30 and above y=288'),
               esd_test=dict(dir='generated/stress-safe-families/single-leg', drc_count=esd['drc_count'], lvs=esd['device_graph_lvs_match'],
                             allocation_um2=round(esd['geometry']['allocation_union_um2']),
                             contents='native Bondpad_5LM on PAD_P (provider bond geometry, wide signal routes) + complete stress-safe macro; PADN terminated to VSS on metal3',
                             note='allocation includes the unused second-leg corridor boxes of the RF pair template (overstated)'),
               layouts=layouts, area_fit=area, runs=summary, run_errors=errors,
               sims_report=dict(path=str(args.sims), sha256=sha(args.sims), models=sims['models'], shunt_model=sims['shunt_model']),
               source_sha256={n: sha(PADS / n) for n in ('stress_safe_families_report.py', 'stress_safe_family_sims.py', 'protection_network_ss.py',
                                                          'rail_shunt_v2.py', 'shunt_wiring_check.py', 'strap_capacity.py', 'stress_safe_usb.py', 'wired_protection_layout_ss.py', 'protection_pad_ss.py', 'stress_safe_wired_layout.py')})
    (G / 'families-report.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(dict(area=area, layouts={k: (v.get('drc_count'), v.get('device_lvs_match', v.get('lvs'))) for k, v in layouts.items()}, runs={k: dict(p=v['pulses']) for k, v in summary.items()}, errors=len(errors)), indent=1))


if __name__ == '__main__':
    main()
