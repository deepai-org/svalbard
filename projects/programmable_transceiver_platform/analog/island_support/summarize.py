"""Collect schematic, physical and extracted results into one compact evidence JSON.

Every verdict is computed from the run outputs named here; a missing input
makes the dependent criterion 'unverified', never 'pass'.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

IMAGE = ('docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3',
         'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305')

# Acceptance limits (design requirements chosen here; see README).
LIM = {
    'drop_v': 0.020,                 # at design current, functional points
    'ring_undershoot_v': 0.010,      # ring dip below its settled value during soft start
    'discharge_s': 50e-6,            # unloaded island rail to < 0.3 V after EN low
    'off_rail_v': 0.5,               # island rail with EN low/undefined during ring ramps/brownout
    'reverse_into_ring_a': 10e-6,    # peer at 3.63 V, ring 0..3.3 V, 0..85 C
    'off_leak_functional_a': 1e-6,   # pass device, 3.35 V, 22..32 C
    'tap_s_off_c_f': 5e-15,          # sense leaf, extracted, at the tapped node
    'tap_off_leak_a': 100e-12,       # tapped node, 22..32 C
    'tap_s_ron_ohm': 30e3,           # accepted: sense path is high impedance (coordinator)
    'pad_overvoltage_ring_i_a': 1e-6,  # atb_pad: current into the ring with PAD at 3.63 V / -0.3 V, 0..85 C
    'pad_overvoltage_bus_v': 0.1,      # global bus stays shunted (internal nodes not exposed)
    'backdrive_into_ring_a': 10e-6,    # RF_TX pad back-drive with the RF island off
    'sense_error_v': 2e-3,           # 10 Mohm meter on ATB1
}


def verdict(ok):
    return 'unverified' if ok is None else ('pass' if ok else 'fail')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def physical(work, cells):
    out = {}
    for c in cells:
        e = {}
        rpt = Path(work, 'drc', c, f'{c}.magic.drc', f'{c}.magic.drc.rpt')
        m = re.search(r'COUNT:\s*(\d+)', rpt.read_text()) if rpt.exists() else None
        e['magic_drc_errors'] = int(m.group(1)) if m else None
        ly = Path(work, 'drc', f'{c}-klayout', f'{c}.klayout.drc', f'{c}.lyrdb')
        e['klayout_drc_violations'] = len(re.findall(r'<item>', ly.read_text())) if ly.exists() else None
        lvs = Path(work, 'lvs', c, f'{c}.magic.lvs', f'{c}.lvs.out')
        if lvs.exists():
            t = lvs.read_text()
            e['lvs'] = ('match' if 'Final result: Circuits match uniquely.' in t and
                        not re.search(r'(?i)property errors were found', t) else 'mismatch')
        else:
            e['lvs'] = None
        pex = Path(work, 'pex', c, f'{c}.pex.spice')
        e['pex_sha256'] = sha(pex) if pex.exists() else None
        gds = Path(work, 'layout', f'{c}.gds')
        e['gds_sha256'] = sha(gds) if gds.exists() else None
        e['clean_physical'] = verdict(None if None in (e['magic_drc_errors'], e['klayout_drc_violations'], e['lvs'])
                                      else e['magic_drc_errors'] == 0 and e['klayout_drc_violations'] == 0
                                      and e['lvs'] == 'match')
        out[c] = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='/work')
    ap.add_argument('--out', default='/work/evidence.json')
    a = ap.parse_args()
    W = Path(a.work)
    S = json.loads((W / 'schematic-result.json').read_text())
    X = json.loads((W / 'extracted-result.json').read_text()) if (W / 'extracted-result.json').exists() else None
    LI = json.loads((W / 'layout' / 'layout-info.json').read_text())
    xc = json.loads((W / 'crosscheck.json').read_text()) if (W / 'crosscheck.json').exists() else None
    RC = json.loads((W / 'rc-result.json').read_text()) if (W / 'rc-result.json').exists() else None
    INT = json.loads((W / 'integration-result.json').read_text()) if (W / 'integration-result.json').exists() else None
    islands = list(S['allocation'])
    cells = [f'isw_{i}' for i in islands] + ['atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad', 'iso_clamp']
    phys = physical(W, cells)
    ev = {'schema': 'island_support_evidence/1', 'image': IMAGE[0], 'image_id': IMAGE[1],
          'pdk_ngspice_sha256': S.get('pdk_ngspice'), 'source_sha256': S.get('source_sha256'),
          'source_sha256_at_summary': {p.name: sha(p) for p in sorted(Path(__file__).resolve().parent.iterdir())
                                       if p.suffix in ('.py', '.sh')},
          'envelope': S['envelope'], 'limits': LIM, 'architecture_source': S['architecture_source']}

    # ---------------- island switch
    isw = {}
    for i in islands:
        al, sz, dr, lk = S['allocation'][i], S['sizes'][i], S['drop'][i], S['off_leakage'][i]
        tr = {k: v for k, v in S['transient'].items() if k.split('_')[2] == i}
        soft = {k: v for k, v in tr.items() if k.startswith('tran_soft_')}
        und = [v['vdd_final'] - v['vdd_min'] for v in soft.values() if 'vdd_min' in v and 'vdd_final' in v]
        abrupt = tr.get(f'tran_abrupt_{i}_tt_27_3.3', {})
        noload = [v.get('t_dis') for k, v in tr.items() if k.startswith('tran_noload_')]
        t_off = 150e-6
        dis = [None if t is None else t - t_off for t in noload]
        rev = S['reverse'][f'bodyswitch/{i}']
        pu = {k: v for k, v in S['powerup_en_floating'].items() if k.split('_')[1] == i}
        bo = {k: v for k, v in S['brownout_repeated_ramps'].items() if k.split('_')[1] == i}
        bo_float = [v.get('visl_max') for k, v in bo.items() if '_float_' in k]
        bo_on_ok = [v.get('pg_end', 0) > 3.0 and v.get('iso_end', 9) < 0.3 for k, v in bo.items() if '_on_' in k]
        xi = (X or {}).get('isw', {}).get(i, {})
        rc = (RC or {}).get('isw', {}).get(i, {})
        xsoft = xi.get('transient', {})
        entry = {
            'blocks': al['blocks'], 'peak_allocation_ma': al['peak_allocation_ma'],
            'design_current_ma': al['design_current_ma'], 'island_decap_f': al['island_decap_f'],
            'pass_device': {'fingers': sz['fingers'], 'w_um': sz['w_um'], 'l_um': sz['l_um'],
                            'array': f"{sz['array_rows']}x{sz['fingers_per_row']}"},
            'layout_area_um2': LI.get(f'isw_{i}', {}).get('area_um2'),
            'drop': {'schematic_functional_max_v': dr['functional_drop_max_v'], 'schematic_tt27_v': dr['drop_tt_27_3v3_v'],
                     'extracted_functional_max_v': xi.get('functional_drop_max_v'),
                     'extracted_tt27_v': xi.get('drop_tt_27_3v3_v'),
                     'exploratory_max_v': dr.get('exploratory_drop_max_v'),
                     'extracted_full_rc_functional_max_v': rc.get('drop_max_v'),
                     'extracted_full_rc_tt27_v': rc.get('drop_tt_27_3v3_v'),
                     'note': ('C-coupled extraction has no resistors, so its DC drop equals the device-only value. '
                              'Full-RC drop is measured between single-point VDD/VISL labels at the M4 plate corners; '
                              'it includes in-cell M3-stripe/M4-plate spreading that a per-row M4 bar + M5 grid fed '
                              'along the array by the top-level ring would largely remove.'),
                     'verdict': verdict(None if rc.get('drop_max_v') is None else
                                        dr['functional_pass'] and xi.get('drop_pass', False) and rc.get('pass', False))},
            'on_state_status': {'pg_high_iso_low_functional': dr['pg_high_all_functional'] and dr['iso_low_all_functional'],
                                'extracted': xi.get('pg_iso_ok')},
            'soft_start': {'ring_undershoot_max_v': max(und) if und else None,
                           'abrupt_reference_undershoot_v': (abrupt.get('vdd_final', 0) - abrupt.get('vdd_min', 0)) if abrupt else None,
                           'switch_current_peak_a': max(v.get('i_peak', 0) for v in soft.values()) if soft else None,
                           'abrupt_switch_current_peak_a': abrupt.get('i_peak'),
                           'rail_10_90_s_range': [min(v['t_on'] - v['t_10'] for v in soft.values() if 't_on' in v and 't_10' in v),
                                                  max(v['t_on'] - v['t_10'] for v in soft.values() if 't_on' in v and 't_10' in v)] if soft else None,
                           'en_to_pg_s_max': max(v['t_pg'] - 20.01e-6 for v in soft.values() if 't_pg' in v) if soft else None,
                           'extracted_ring_undershoot_max_v': max((v['vdd_final'] - v['vdd_min'] for v in xsoft.values() if 'vdd_min' in v), default=None),
                           'verdict': verdict(None if not und else max(und) <= LIM['ring_undershoot_v'])},
            'discharge': {'unloaded_rail_to_0v3_s': dis,
                          'verdict': verdict(None if (not dis or None in dis) else max(dis) <= LIM['discharge_s'])},
            'iso_on_disable_s_max': max((v['t_isooff'] - t_off for v in soft.values() if 't_isooff' in v), default=None),
            'off_leakage': {**lk, 'verdict': verdict(lk['functional_max_a_3v35_22to32c'] <= LIM['off_leak_functional_a'])},
            'reverse_blocking': {'max_i_into_ring_a': rev['max_i_into_ring_a'], 'max_i_from_peer_a': rev['max_i_from_peer_a'],
                                 'max_i_from_peer_ring_unpowered_a': rev['max_i_from_peer_ring_unpowered_a'],
                                 'note': 'Peer current with the ring powered is the active-discharge NMOS sinking from the back-driven rail.',
                                 'verdict': verdict(rev['max_i_into_ring_a'] <= LIM['reverse_into_ring_a'])},
            'default_off': {'en_floating_ramp_visl_max_v': max(v.get('visl_max', 9) for v in pu.values()) if pu else None,
                            'iso_high_after_ramp': all(v.get('iso_end', 0) > 3.0 for v in pu.values()) if pu else None,
                            'brownout_en_floating_visl_max_v': max(x for x in bo_float if x is not None) if bo_float else None,
                            'brownout_en_on_recovers': all(bo_on_ok) if bo_on_ok else None,
                            'verdict': verdict(None if not pu or not bo_float else
                                               max(v.get('visl_max', 9) for v in pu.values()) <= LIM['off_rail_v'] and
                                               max(bo_float) <= LIM['off_rail_v'] and all(bo_on_ok))},
            'physical': phys.get(f'isw_{i}'),
        }
        isw[i] = entry
    ev['island_switch'] = isw
    bd = S.get('rf_tx_backdrive')
    if bd:
        c = bd['cases']
        def sel(f):
            return [v for k, v in c.items() if f(k.split('_'))]
        ev['rf_tx_backdrive'] = {
            'model': bd['model'],
            'calibration_i_into_0v_rail_a_range': [min(v['i_pad'] for v in sel(lambda p: p[-1] == '0' and p[5] == '3.3')),
                                                   max(v['i_pad'] for v in sel(lambda p: p[-1] == '0' and p[5] == '3.3'))],
            'max_i_into_ring_a': max(v['i_into_ring'] for v in c.values()),
            'decap_only': {'visl_range_v': [min(v['visl_v'] for v in sel(lambda p: p[-1] == 'None')),
                                            max(v['visl_v'] for v in sel(lambda p: p[-1] == 'None'))],
                           'i_pad_max_a': max(v['i_pad'] for v in sel(lambda p: p[-1] == 'None'))},
            'with_island_load': {'visl_range_v': [min(v['visl_v'] for v in sel(lambda p: p[-1] not in ('0', 'None'))),
                                                  max(v['visl_v'] for v in sel(lambda p: p[-1] not in ('0', 'None')))],
                                 'i_pad_max_a': max(v['i_pad'] for v in sel(lambda p: p[-1] not in ('0', 'None')))},
            'iso_high_when_ring_powered': all(v['iso_v'] > 3.0 for v in sel(lambda p: p[4] == '3.3')),
            'pg_high_when_ring_powered_decap_only': all(v['pg_v'] > 3.0 for v in sel(lambda p: p[4] == '3.3' and p[-1] == 'None')),
            'verdict': verdict(max(v['i_into_ring'] for v in c.values()) <= LIM['backdrive_into_ring_a']),
            'extracted': (X or {}).get('rf_tx_backdrive'),
        }
    ev['reverse_topology_comparison_wired'] = {k: {kk: vv for kk, vv in v.items() if kk != 'cases'}
                                               for k, v in S['reverse'].items() if k.endswith('/wired')}

    # ---------------- ATB
    A = S['atb']
    XA = (X or {}).get('atb', {})
    atb = {}
    for c in ['atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad']:
        e = {'schematic_ron_functional_max_ohm': A['ron'][c]['functional_max_ohm'],
             'schematic_ron_tt27_max_ohm': A['ron'][c]['tt_27_3v3_max_ohm'],
             'extracted_ron_functional_max_ohm': XA.get(c, {}).get('ron_functional_max_ohm'),
             'bbm_min_gap_s_schematic': A['break_before_make'][c]['min_gap_between_cells_s'],
             'bbm_min_gap_s_extracted': XA.get(c, {}).get('bbm_min_gap_between_cells_s'),
             'bbm_min_internal_gap_s_extracted': XA.get(c, {}).get('bbm_min_internal_gap_s'),
             'layout_area_um2': LI.get(c, {}).get('area_um2'), 'physical': phys.get(c)}
        if c in A['off_node_loading']:
            o = A['off_node_loading'][c]
            e.update({'off_c_schematic_max_f': o['c_max_f'],
                      'off_c_extracted_max_f': XA.get(c, {}).get('off_c_max_f'),
                      'off_c_extracted_tt22_mid_f': XA.get(c, {}).get('off_c_tt_22_mid_f'),
                      'off_leak_schematic_max_22to32c_a': o['leak_abs_max_functional_a'],
                      'off_leak_extracted_max_22to32c_a': XA.get(c, {}).get('off_leak_abs_max_22to32c_a'),
                      'off_leak_schematic_85c_a': o['leak_abs_max_85c_a'],
                      'isolation_schematic': {k: v for k, v in A['isolation_db_into_10k_node'].items() if k.startswith(f'iso_{c}_')},
                      'isolation_extracted_tt27': XA.get(c, {}).get('isolation_db_into_10k_node_tt27')})
        atb[c] = e
    gaps = [atb[c]['bbm_min_gap_s_extracted'] for c in atb]
    atb['verdicts'] = {
        'sense_tap_off_loading': verdict(None if atb['atb_leaf_s'].get('off_c_extracted_max_f') is None else
                                         atb['atb_leaf_s']['off_c_extracted_max_f'] <= LIM['tap_s_off_c_f']),
        'tap_off_leakage': verdict(None if atb['atb_leaf_s'].get('off_leak_extracted_max_22to32c_a') is None else
                                   max(atb[c]['off_leak_extracted_max_22to32c_a'] for c in ('atb_leaf_s', 'atb_leaf_f')) <= LIM['tap_off_leak_a']),
        'sense_tap_ron': verdict(None if atb['atb_leaf_s']['extracted_ron_functional_max_ohm'] is None else
                                 atb['atb_leaf_s']['extracted_ron_functional_max_ohm'] <= LIM['tap_s_ron_ohm']),
        'break_before_make': verdict(None if None in gaps else min(gaps) > 0),
        'pad_overvoltage': verdict(
            max(abs(v['i_ring']) for v in A['pad_overvoltage']['cases'].values()) <= LIM['pad_overvoltage_ring_i_a'] and
            A['pad_overvoltage']['max_abs_vbus_v'] <= LIM['pad_overvoltage_bus_v'] and
            all(abs(v.get('i_ring', 0)) <= LIM['pad_overvoltage_ring_i_a'] and abs(v.get('vbus', 0)) <= LIM['pad_overvoltage_bus_v']
                for v in (XA.get('pad_overvoltage') or {}).values())),
        'force_sense': verdict(max(abs(v['sense_error']) for v in A['force_sense'].values()) <= LIM['sense_error_v']),
    }
    atb['select_glitch_schematic'] = A.get('select_glitch')
    atb['register_gap_spec_s'] = A.get('break_before_make_gap_spec_s')
    atb['lvsmode_off_c_tt22_mid_f'] = (X or {}).get('atb_lvsmode_off_c_tt22_mid_f')
    atb['pad_overvoltage_schematic'] = {k: v for k, v in A['pad_overvoltage'].items() if k != 'cases'}
    atb['pad_overvoltage_schematic']['max_abs_i_ring_a'] = max(abs(v['i_ring']) for v in A['pad_overvoltage']['cases'].values())
    atb['pad_overvoltage_extracted'] = XA.get('pad_overvoltage')
    atb['force_sense_schematic'] = A['force_sense']
    atb['force_sense_extracted'] = XA.get('force_sense')
    atb['sense_settling_schematic'] = A['sense_settling']
    atb['sense_settling_extracted'] = XA.get('sense_settling')
    # Hierarchy: 8 groups x 12 leaves. Disabled loading on shared buses from extracted off C.
    cs = atb['atb_leaf_s'].get('off_c_extracted_max_f')
    cg = atb['atb_grp'].get('off_c_extracted_max_f')
    atb['hierarchy'] = {'groups': 8, 'leaves_per_group': 12, 'nodes': 96, 'force_capable_per_group': 4,
                        'select_bits': {'group': 3, 'leaf': 4, 'bus_enable': 2},
                        'local_bus_off_load_estimate_f': None if cs is None else 11 * cs,
                        'global_bus_off_load_estimate_f': None if cg is None else 7 * cg,
                        'note': ('Uses node-side extracted off capacitance per cell. atb_leaf_s has a larger T2 on its bus '
                                 'side (1/2 um vs 0.42/0.84 um T1), so the local-bus figure is a lower bound. Bus wiring excluded.')}
    ev['atb'] = atb
    atb['notes'] = [
        'Ron, DC leakage and force/sense DC values are identical between schematic and C-coupled extracted netlists by construction (no extracted resistance at DC); extracted capacitance changes only AC/transient results.',
        ('ATB cells are simulated on a default-mode ext2spice C-coupled extraction (pexd). sak-pex runs ext2spice in lvs mode, '
         'which moved the substrate capacitance of gate-only nets (SEL 6.27 fF + SWB 4.52 fF in atb_leaf_s) in equal halves onto '
         'NODE and MID (+5.40 fF each); the default mode keeps NODE at its .ext value (0.47 fF to substrate). '
         'atb.lvsmode_off_c_tt22_mid_f records the lvs-mode figure for comparison.'),
        ('Bare leaves have no internal TG/shunt non-overlap; a switching leaf briefly overlaps (~0.1-0.2 ns). '
         'atb.select_glitch_schematic gives the resulting disturbance on a 1 pF / 10 pF, 100 kohm-fed bias node.'),
        'atb_pad auto-bulk dead zone: with the ring at 3.3 V and PAD at 3.63 V (|PAD-VDD| below |Vtp|) VMAX is not driven; one extracted DC case conducts ~56 uA PAD -> bus -> shunt to VSS (bus 45 mV, ring current < 1 nA). Not a ring back-drive, but a bench load on the ATB pad.',
    ]
    ev['physical'] = phys
    ev['physical_crosscheck_librelane_image'] = xc
    if INT:
        ev['integration_rf_tx_backdrive_iso'] = {k: {kk: vv for kk, vv in v.items() if kk != 'cases'} for k, v in INT.items()}
    areas = {c: LI.get(c, {}).get('area_um2') for c in cells}
    ev['area'] = {'cells_um2': areas,
                  'island_switches_total_mm2': round(sum(areas[f'isw_{i}'] or 0 for i in islands) / 1e6, 4),
                  'atb_tree_96_node_mm2': round((96 * (areas['atb_leaf_s'] or 0) + 32 * (areas['atb_leaf_f'] or 0)
                                                 + 16 * (areas['atb_grp'] or 0) + 2 * (areas['atb_pad'] or 0)) / 1e6, 4),
                  'atb_tree_target_mm2': 0.30,
                  'note': ('Bounding-box areas, no routing. ATB tree: 96 bare sense leaves, 32 bare force-capable '
                           'leaves (4 per group; the register map allows ATB0 on 20 codes), 16 group switches '
                           '(8 per bus, with the default-open/break-before-make control), 2 pad switches.'),
                  'reserve_granted_mm2': 0.35}
    dc_path = Path(__file__).resolve().parent.parent.parent / 'spec' / 'debug-controls.json'
    if dc_path.exists():
        nodes = json.loads(dc_path.read_text())['atb_nodes']
        hw = [n for n in nodes if n.get('hardware', True)]
        n_s = len(hw)
        n_f = sum(1 for n in hw if n['force'] in ('override', 'allowed'))
        g_s, g_f = -(-n_s // 12), -(-n_f // 12)
        ev['area']['atb_tree_register_map'] = {
            'source': 'spec/debug-controls.json atb_nodes (hardware != false)', 'sense_leaves': n_s,
            'force_leaves': n_f, 'groups_sense_bus': g_s, 'groups_force_bus': g_f, 'pad_switches': 2,
            'mm2': round((n_s * (areas['atb_leaf_s'] or 0) + n_f * (areas['atb_leaf_f'] or 0)
                          + (g_s + g_f) * (areas['atb_grp'] or 0) + 2 * (areas['atb_pad'] or 0)) / 1e6, 4),
            'placement': ('Sense leaves for per-block bias nodes sit at the core_support bias-bank outputs '
                          '(same observability as the mirror gate, shorter routing); one leaf per register-map code.')}
    allclean = all(p['clean_physical'] == 'pass' for p in phys.values())
    xok = X is not None and all(isw[i]['drop']['verdict'] == 'pass' for i in islands)
    safe_keys = ('default_off', 'reverse_blocking', 'discharge', 'off_leakage')
    safe_ok = (all(isw[i][k]['verdict'] == 'pass' for i in islands for k in safe_keys)
               and ev.get('rf_tx_backdrive', {}).get('verdict') == 'pass'
               and atb['verdicts']['pad_overvoltage'] == 'pass'
               and all(v.get('verdict') == 'pass' for v in (INT or {'x': {}}).values()))
    clean_ok = allclean and all(isw[i]['drop']['verdict'] == 'pass' for i in islands) and all(
        atb['verdicts'][k] == 'pass' for k in ('sense_tap_off_loading', 'tap_off_leakage', 'sense_tap_ron', 'break_before_make'))
    readiness = {
        'safe': 'pass' if safe_ok else 'open',
        'clean': 'pass' if clean_ok else 'open',
        'observable': 'open',
        'fallback': 'waived_core',
        'scope': ('Island switches + ATB cells + iso_clamp, cell level plus the RF_TX back-drive integration fixture. '
                  '"observable" stays open: PG/ISO/EN register fields and the ATB select decode are not in rtl/. '
                  '"clean" covers the switch/ATB cells; ring decap and top-level assembly belong to later freeze stages.'),
        'evidence': {'safe': ['island_switch.*.{default_off,reverse_blocking,discharge,off_leakage}', 'rf_tx_backdrive',
                              'integration_rf_tx_backdrive_iso', 'atb.verdicts.pad_overvoltage'],
                     'clean': ['physical', 'physical_crosscheck_librelane_image', 'island_switch.*.drop', 'atb.verdicts']},
    }
    ev['summary'] = {
        'all_cells_drc_lvs_clean': allclean,
        'extracted_function_all_islands': xok,
        'proposed_tapeout_readiness_power': readiness,
    }
    Path(a.out).write_text(json.dumps(ev, indent=1, default=str))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
