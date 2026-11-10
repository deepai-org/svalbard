#!/usr/bin/env python3
"""Collect the core-support clean/sim outputs into compact evidence.

Reads scratch outputs left by clean_flow.sh, crosscheck_canary.sh and
sim_core_support.py.  Writes evidence/core_support_evidence.json (configuration, stimulus,
criterion, outcome, source hashes, exclusions).
Every outcome is derived from a tool output file; nothing is typed in by hand.
"""
import argparse
import glob
import hashlib
import json
import os
import re
from statistics import median

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # analog/core_support


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def rel(p):
    return os.path.relpath(p, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE)))))


# Netgen strings that make an LVS run a failure wherever they appear in the
# report.  "Netlists do not match" is also a failure unless netgen flattened
# exactly that (sub)circuit pair afterwards and compared again; a top-level
# occurrence is never resolved.
NETGEN_FAILURES = ('failed pin matching', 'Property errors were found', 'had property errors',
                   'Netlists do not match', 'no matching pin', 'Top level cell failed',
                   'Cells have no pins in common', 'has no elements', 'Fatal error')


def lvs_result(path):
    """Strict reading of one netgen comparison report.

    match is True only if the final verdict is a unique match AND none of the
    NETGEN_FAILURES strings appears, except a subcircuit "Netlists do not match"
    that netgen itself resolved by flattening that subcircuit pair and
    re-comparing (recorded in flattened_subcells).  Property errors, pin
    mismatches and top-level non-matches are always failures.
    """
    txt = read(path)
    if txt is None:
        return {'file': rel(path), 'result': 'missing', 'match': False}
    lines = txt.splitlines()
    fin = [l for l in lines if l.startswith('Final result')]
    nets = [l for l in lines if l.startswith('Number of nets')]
    devs = [l for l in lines if l.startswith('Number of devices')]
    final = fin[-1].split(':', 1)[1].strip() if fin else 'no final result'
    failures, flattened, dangling = [], [], []
    for i, l in enumerate(lines):
        for f in NETGEN_FAILURES:
            if f not in l:
                continue
            if f == 'Netlists do not match' and l.strip() == 'Netlists do not match.':
                # resolved only if the next "Flattening non-matched subcircuits" follows
                # before the next comparison verdict and the run continues to a top match
                tail = lines[i+1:i+4]
                m = [t for t in tail if 'Flattening non-matched subcircuits' in t]
                if m:
                    flattened.append(m[0].strip())
                    continue
            if f == 'no matching pin':
                # A Magic auto-named node (a_<x>_<y>#) that netgen itself lists as a
                # "disconnected node" of the layout cell is an unconnected extraction
                # artifact, not a missing schematic pin.  Anything else fails.
                port = l.split('|')[0].strip()
                leaf = port.split('/')[-1]
                if re.fullmatch(r'a_\d+_\d+#', leaf) and any(
                        'disconnected node: ' + leaf in t or 'disconnected node: ' + port in t for t in lines):
                    dangling.append(port)
                    continue
            failures.append({'line': i+1, 'text': l.strip()})
    pin_mismatch = 0
    blocks = [i for i, l in enumerate(lines) if l.startswith('Subcircuit pins:')]
    if blocks:
        for l in lines[blocks[-1]+1:]:
            if l.startswith(('Cell pin lists', 'Final result', 'Device classes')):
                break
            pin_mismatch += l.count('**Mismatch**')
    unique = final.startswith('Circuits match uniquely')
    return {'file': rel(path), 'final': final,
            'match': unique and not failures and not pin_mismatch,
            'failure_strings': failures[:20], 'failure_count': len(failures),
            'top_pin_mismatches': pin_mismatch,
            'flattened_subcells': flattened,
            'accepted_dangling_extraction_ports': sorted(set(dangling)),
            'top_nets': re.sub(r'\s+', ' ', nets[-1]) if nets else None,
            'top_devices': re.sub(r'\s+', ' ', devs[-1]) if devs else None}


def klayout_result(d):
    log = read(os.path.join(d, 'klayout_drc.log'))
    if log is None:
        return {'result': 'not_run'}
    m = re.findall(r'DRC RESULT: (\w+) \((\d+) violations\)', log)
    lyrdb = os.path.join(d, 'klayout_drc.lyrdb')
    items = None
    if os.path.exists(lyrdb):
        items = read(lyrdb).count('<item>')
    if not m:
        return {'result': 'no_result_line', 'lyrdb_items': items}
    return {'result': m[-1][0], 'violations': int(m[-1][1]), 'lyrdb_items': items,
            'deck': 'gf180mcu.drc feol beol conn_drc wedge, decks=all,-density, run_mode=deep'}


def pex_stats(path):
    if not os.path.exists(path):
        return None
    c = r = x = 0
    with open(path) as f:
        for line in f:
            if line[:1] in 'Cc' and not line.startswith('*'):
                c += 1
            elif line[:1] in 'Rr':
                r += 1
            elif line[:1] in 'Xx':
                x += 1
    return {'capacitors': c, 'resistors': r, 'devices_and_subckts': x, 'sha256': sha256(path)}


def clean_block(work, blk):
    d = os.path.join(work, 'clean', blk)
    if not os.path.isdir(d):
        return {'result': 'not_run'}
    drc = read(os.path.join(d, 'magic_drc.txt'), '')
    tot = re.search(r'total: (\d+)', drc)
    gds = read(os.path.join(d, 'gds_checked.txt'))
    gds_host = gds.replace('/work/', work + '/') if gds else None
    out = {
        'schematic_netlist_regenerated_from_xschem': read(os.path.join(d, 'sch_vs_vendored.txt')),
        'magic_drc': {'style': 'drc(full)', 'errors': int(tot.group(1)) if tot else None},
        'klayout_drc': klayout_result(d),
        'gds_checked': {'path_in_container': gds,
                        'sha256': sha256(gds_host) if gds_host and os.path.exists(gds_host) else None},
        'lvs_magic_hierarchical': lvs_result(os.path.join(d, 'lvs_comp.out')),
        'lvs_gds_flat': lvs_result(os.path.join(d, 'lvs_gds_comp.out')),
        'pex_mode': read(os.path.join(d, 'pex_mode.txt')),
        'pex_rc_failure': read(os.path.join(d, 'pex_rc_failure.txt')),
        'pex_netlist': pex_stats(os.path.join(d, 'layout_pex.spice')),
        'hres_check': json.load(open(os.path.join(d, 'hres_check.json'))) if os.path.exists(os.path.join(d, 'hres_check.json')) else None,
        'xor_vs_vendored_gds': json.load(open(os.path.join(d, 'xor_vs_vendored.json'))) if os.path.exists(os.path.join(d, 'xor_vs_vendored.json')) else None,
        'magic_drc_breakdown': [l for l in read(os.path.join(d, 'magic_drc.txt'), '').splitlines()[2:]],
    }
    if blk.endswith('_patched'):
        out['tapeout_export'] = 'analog image Magic 8.3.678, Avalon std cells read from GDS, cif ostyle gdsii, gds compress 9 + lef write -hide'
    for k, f in (('lvs_magic_hierarchical_common_ground', 'lvs_comp_tiedgnd.out'),
                 ('lvs_gds_flat_common_ground', 'lvs_gds_comp_tiedgnd.out'),
                 ('lvs_magic_hierarchical_pnp_alias', 'lvs_comp_pnpalias.out'),
                 ('lvs_gds_flat_pnp_alias', 'gds_comp_pnpalias.out')):
        if os.path.exists(os.path.join(d, f)):
            out[k] = lvs_result(os.path.join(d, f))
    cd = os.path.join(work, 'canary', blk)
    if os.path.isdir(cd):
        cdrc = re.search(r'total: (\d+)', read(os.path.join(cd, 'magic_drc.txt'), ''))
        out['canary_crosscheck'] = {
            'tools': read(os.path.join(cd, 'tool_versions.txt'), '').splitlines()[:2],
            'magic_drc_errors': int(cdrc.group(1)) if cdrc else None,
            'lvs': lvs_result(os.path.join(cd, 'lvs_comp.out')),
        }
        nc = os.path.join(cd, 'hres_negative_control.json')
        if os.path.exists(nc):
            out['canary_crosscheck']['hres_negative_control_canary_gds_export'] = json.load(open(nc))
        if os.path.exists(os.path.join(cd, 'lvs_comp_tiedgnd.out')):
            out['canary_crosscheck']['lvs_common_ground'] = lvs_result(os.path.join(cd, 'lvs_comp_tiedgnd.out'))
    return out


def load_results(work, pattern):
    recs = []
    for p in glob.glob(os.path.join(work, 'sim', pattern)):
        recs += json.load(open(p))
    return recs


# ------------------------------------------------------------------ POR criteria
FUNC_DELAY_MIN, FUNC_DELAY_MAX = 5e-3, 500e-3


def por_clean_reset(r):
    """Reset asserted at first valid supply, exactly one release, none after."""
    return (r.get('first_valid_state') == 'asserted' and len(r.get('release_times_s', [])) == 1
            and not r.get('assert_times_s') and r.get('final_state') == 'released')


def por_function_ok(r):
    d = r.get('delay_after_vdd_90pct_s')
    return (por_clean_reset(r) and not r.get('released_before_vdd_90pct')
            and d is not None and FUNC_DELAY_MIN <= d <= FUNC_DELAY_MAX)


def por_row(r):
    return {k: r.get(k) for k in ('corner', 'temp_c', 'trise_s', 'vfinal_v', 'netlist', 'release_vdd_v',
                                  'delay_from_ramp_start_s', 'delay_after_vdd_90pct_s',
                                  'released_before_vdd_90pct', 'final_supply_current_a', 'error')}


def summarize_por(recs):
    out = {}
    ramps = [r for r in recs if r.get('kind') == 'por_ramp']
    errors = [r['job'] for r in recs if 'error' in r]
    func_pts = {('typical', 27, 3.3)} | {(c, T, v) for c in ('typical', 'ff', 'ss') for T in (22, 32)
                                         for v in (3.15, 3.35)}
    for net in ('schematic', 'pex'):
        rows = [r for r in ramps if r.get('netlist') == net and r.get('trise_s') == 1e-4
                and (r['corner'], r['temp_c'], r['vfinal_v']) in func_pts]
        ok = [r for r in rows if 'error' not in r and por_function_ok(r)]
        out['function_window_' + net] = {
            'stimulus': 'VDD 0 -> {3.15, 3.35} V in 100 us (plus nominal 3.3 V), tt/ss/ff x 22/32 C; ena tied to VDD; 1 pF on por/porb',
            'criterion': 'porb asserted when VDD first reaches 1.0 V; exactly one release; no re-assertion; '
                         'release after VDD >= 90%% of final; %g ms <= delay after VDD 90%% <= %g ms'
                         % (FUNC_DELAY_MIN * 1e3, FUNC_DELAY_MAX * 1e3),
            'points': len(rows), 'pass': len(ok),
            'outcome': 'pass' if rows and len(ok) == len(rows) == len(func_pts) else
                       ('fail' if rows else 'not_run'),
            'delay_after_vdd90_s_min_max': [min(r['delay_after_vdd_90pct_s'] for r in ok),
                                            max(r['delay_after_vdd_90pct_s'] for r in ok)] if ok else None,
            'supply_current_a_min_max': [min(r['final_supply_current_a'] for r in ok),
                                         max(r['final_supply_current_a'] for r in ok)] if ok else None,
            'rows': [por_row(r) for r in sorted(rows, key=lambda r: (r['corner'], r['temp_c'], r['vfinal_v']))],
        }
    # PEX vs schematic at identical points
    pairs = []
    for r in ramps:
        if r.get('netlist') == 'pex' and 'error' not in r:
            s = next((q for q in ramps if q.get('netlist') == 'schematic' and q['corner'] == r['corner']
                      and q['temp_c'] == r['temp_c'] and q['vfinal_v'] == r['vfinal_v']
                      and q['trise_s'] == r['trise_s'] and 'error' not in q), None)
            if s and s.get('delay_after_vdd_90pct_s') and r.get('delay_after_vdd_90pct_s'):
                pairs.append((r['delay_after_vdd_90pct_s'] / s['delay_after_vdd_90pct_s'] - 1) * 100)
    out['pex_vs_schematic_delay_pct'] = {'n': len(pairs), 'min': min(pairs) if pairs else None,
                                         'max': max(pairs) if pairs else None}
    # Safety ramps to 3.63 V
    safe = [r for r in ramps if r.get('vfinal_v') == 3.63]
    bad = [r for r in safe if 'error' in r or not por_clean_reset(r)]
    early = [r for r in safe if r.get('released_before_vdd_90pct')]
    good = [r for r in safe if r not in bad]
    out['safety_ramps_3v63'] = {
        'stimulus': 'VDD 0 -> 3.63 V, rise 1 us/10 us/1 ms/10 ms/100 ms/1 s, tt/ss/ff x 0/27/85 C (schematic netlist)',
        'criterion': 'clean reset on every ramp: porb asserted at first valid supply (VDD >= 1.0 V), '
                     'exactly one release, no glitch/re-assertion, released at the end',
        'points': len(safe), 'clean_reset': len(safe) - len(bad),
        'outcome': 'pass' if safe and not bad else ('fail' if safe else 'not_run'),
        'failures': [por_row(r) for r in bad],
        'released_before_vdd_90pct_count': len(early),
        'clean_reset_release_vdd_v_by_rise_time': {
            '%g' % tr: [min(r['release_vdd_v'] for r in good if r['trise_s'] == tr),
                        max(r['release_vdd_v'] for r in good if r['trise_s'] == tr)]
            for tr in sorted({r['trise_s'] for r in good})},
        'clean_reset_delay_from_ramp_start_s_by_rise_time': {
            '%g' % tr: [min(r['delay_from_ramp_start_s'] for r in good if r['trise_s'] == tr),
                        max(r['delay_from_ramp_start_s'] for r in good if r['trise_s'] == tr)]
            for tr in sorted({r['trise_s'] for r in good})},
        'rows': [por_row(r) for r in sorted(safe, key=lambda r: (r['corner'], r['temp_c'], r['trise_s']))],
    }
    nom = [r for r in ramps if r['corner'] == 'typical' and r['temp_c'] == 27 and r['vfinal_v'] == 3.3
           and r.get('netlist') == 'schematic']
    out['nominal_ramp_sweep_3v3'] = [por_row(r) for r in sorted(nom, key=lambda r: r['trise_s'])]
    expl = [r for r in ramps if r['temp_c'] in (-40, 125)]
    out['exploratory_minus40_125C'] = [por_row(r) for r in sorted(expl, key=lambda r: (r['temp_c'], r['trise_s']))]
    # brownout dips
    dips = [r for r in recs if r.get('kind') == 'por_dip']
    cold = median([r['delay_after_vdd_90pct_s'] for r in ramps if r.get('delay_after_vdd_90pct_s')
                   and r['corner'] == 'typical' and r['temp_c'] == 27] or [0.039])

    def classify(r):
        h = r.get('reset_hold_after_recovery_s')
        if h is None:
            return 'held_to_end_of_run'
        if h == 0.0:
            return 'no_reset_after_recovery'
        return 'full_reset' if h >= 0.5 * cold else 'partial_reset'
    out['brownout_dips'] = {
        'stimulus': 'cold start (100 us ramp to 3.3 V, released), then VDD dips to Vdip for tdip with 10 us edges, back to 3.3 V',
        'criterion': 'informational: does the POR re-issue a reset after the dip (full = hold >= 50% of the cold-start delay)',
        'cold_start_delay_reference_s': cold,
        'rows': [{'corner': r['corner'], 'temp_c': r['temp_c'], 'vdip_v': r.get('vdip_v'), 'tdip_s': r.get('tdip_s'),
                  'class': classify(r), 'reset_hold_after_recovery_s': r.get('reset_hold_after_recovery_s'),
                  'reset_asserted_with_vdd_ge_1v': r.get('reset_asserted_with_vdd_ge_1v'),
                  'vcap_at_recovery_v': r.get('vcap_at_recovery_v'), 'released_at_end': r.get('released_at_end'),
                  'error': r.get('error')}
                 for r in sorted(dips, key=lambda r: (r['corner'], r['temp_c'], -r.get('vdip_v', 0), r.get('tdip_s', 0)))],
    }
    reps = [r for r in recs if r.get('kind') == 'por_repeat']
    out['repeated_ramps'] = {
        'stimulus': 'cold start, then VDD 3.3 -> 0 V in 100 us, off for toff, 0 -> 3.3 V in 100 us',
        'criterion': 'informational: reset hold after the second ramp (full = >= 50% of cold-start delay)',
        'rows': [{'corner': r['corner'], 'temp_c': r['temp_c'], 'toff_s': r.get('toff_s'), 'class': classify(r),
                  'reset_hold_after_recovery_s': r.get('reset_hold_after_recovery_s'),
                  'vcap_at_recovery_v': r.get('vcap_at_recovery_v'), 'released_at_end': r.get('released_at_end'),
                  'error': r.get('error')}
                 for r in sorted(reps, key=lambda r: (r['corner'], r['temp_c'], r.get('toff_s', 0)))],
    }
    falls = [r for r in recs if r.get('kind') == 'por_fall']
    out['falling_rail'] = {
        'stimulus': 'cold start, then VDD 3.3 -> 0 V in tfall',
        'criterion': 'informational: is reset asserted while VDD is still >= 1.0 V',
        'rows': [{'corner': r['corner'], 'temp_c': r['temp_c'], 'tfall_s': r.get('tfall_s'),
                  'reset_asserted_with_vdd_ge_1v': r.get('reset_asserted_with_vdd_ge_1v'),
                  'assert_vdd_v': r.get('assert_vdd_v'), 'error': r.get('error')}
                 for r in sorted(falls, key=lambda r: (r['corner'], r['temp_c'], r.get('tfall_s', 0)))],
    }
    out['simulation_errors'] = errors
    return out


# -------------------------------------------------------------- biasgen criteria
def summarize_bg(recs):
    out = {}
    dcs = [r for r in recs if r.get('kind') == 'bg_dc']
    errors = [r['job'] for r in recs if 'error' in r]
    unit_expected = 250e-9

    def unit_table(rs, key):
        rows = []
        for r in sorted(rs, key=lambda r: (r['mode'], r['corner'], r['temp_c'])):
            if 'error' in r:
                rows.append({'job': r['job'], 'error': r['error'][-300:]})
                continue
            for v in ('3.15', '3.30', '3.35'):
                cur = r['currents_a'][v]
                rows.append({'mode': r['mode'], 'corner': r['corner'], 'temp_c': r['temp_c'], 'netlist': r['netlist'],
                             'supply_v': float(v),
                             'idac1_code4_a': cur['idac1_source_ibias'], 'idac2_code31_a': cur['idac2_source_ibias'],
                             'bandgap_sink1_code4_a': -cur['bandgap_sink1_ibias'],
                             'bandgap_sink2_code1_a': -cur['bandgap_sink2_ibias'],
                             'supply_current_a': cur['supply_current_a']})
        return rows
    for net in ('schematic', 'pex'):
        rs = [r for r in dcs if r['netlist'] == net and r['ena'] == 'vdd' and r['temp_c'] in (22, 27, 32)]
        out['window_currents_' + net] = unit_table(rs, net)
    sens = {}
    for r in dcs:
        if 'error' in r or r['netlist'] != 'schematic' or r['ena'] != 'vdd' or r['temp_c'] not in (22, 27, 32):
            continue
        sens.setdefault(r['mode'], []).append(r['supply_sensitivity_pct_per_v_3v15_3v35'])
    out['supply_sensitivity_pct_per_v_3v15_3v35'] = {
        m: {o: [min(x[o] for x in v if x[o] is not None), max(x[o] for x in v if x[o] is not None)]
            for o in ('idac1_source_ibias', 'bandgap_sink1_ibias')} for m, v in sens.items()}
    off = [r for r in dcs if r['ena'] == 'off']
    out['disabled'] = [{'corner': r['corner'], 'temp_c': r['temp_c'],
                        'currents_at_3v30_a': r.get('currents_a', {}).get('3.30'), 'error': r.get('error')} for r in off]
    expl = [r for r in dcs if r['temp_c'] in (-40, 125)]
    out['exploratory_minus40_125C'] = unit_table(expl, 'schematic')
    tr = [r for r in recs if r.get('kind') == 'bg_tran']
    dc_ref = {(r['corner'], r['temp_c'], r['mode'], r['netlist']): r for r in dcs if 'error' not in r and r['ena'] == 'vdd'}
    rows, starts = [], 0
    for r in sorted(tr, key=lambda r: (r['mode'], r['corner'], r['temp_c'], r['trise_s'])):
        if 'error' in r:
            rows.append({'job': r['job'], 'error': r['error'][-300:]})
            continue
        f = r['final_currents_a']
        ref = dc_ref.get((r['corner'], r['temp_c'], r['mode'], r['netlist']))
        if ref:
            want = ref['currents_a']['3.30']
            ok = all(abs(f[o] - want[o]) <= 0.05 * abs(want[o]) for o in ('idac1_source_ibias', 'bandgap_sink1_ibias'))
            basis = 'within 5% of DC operating point'
        else:
            ok = f['idac1_source_ibias'] > 1e-9 and -f['bandgap_sink1_ibias'] > 1e-9
            basis = 'no DC point at this temperature: idac1 and sink1 > 1 nA'
        starts += ok
        rows.append({'mode': r['mode'], 'corner': r['corner'], 'temp_c': r['temp_c'], 'trise_s': r['trise_s'],
                     'netlist': r['netlist'], 'started': ok, 'criterion_basis': basis,
                     'idac1_final_a': f['idac1_source_ibias'], 'bandgap_sink1_final_a': -f['bandgap_sink1_ibias'],
                     'idac1_settle_5pct_after_vdd_3v0_s': r.get('idac1_settle_5pct_after_vdd_3v0_s'),
                     'supply_current_a': r['final_supply_current_a']})
    out['startup'] = {
        'stimulus': 'VDD (avdd=dvdd=ref_in) 0 -> 3.3 V in 1 us/100 us/10 ms (100 ms nominal), ena and trim bits tied to VDD/0, '
                    'tt/ss/ff x 0/27/85 C; sources into 1.0 V, sinks from VDD-1.0 V',
        'criterion': 'no zero-current or stuck state: at the end of every ramp idac1 and bandgap_sink1 are within 5% '
                     'of the DC operating point (27 C; at 0/85 C, where no DC point was run, both must exceed 1 nA)',
        'points': len(rows), 'started': starts,
        'outcome': 'pass' if rows and starts == len(rows) else ('fail' if rows else 'not_run'),
        'rows': rows,
    }
    probes = [r for r in recs if r.get('kind') == 'bg_probe']
    fixed = [r for r in probes if r.get('netlist') in ('schematic', 'pex')]
    upstream = [r for r in probes if r.get('netlist') == 'vendored']
    out['bandgap_mode_probes'] = {
        'stimulus': 'ref_sel_vbg=1 (idac1 code 4); events: VDD 0->V in 1 us or 10 us (vbg static 1.2 V or tracking '
                    'min(VDD,1.2)); ena or ref_sel_vbg 0->1 with 1 us edge at 50 us on a settled supply; '
                    '150 mV supply step; .tran step ceiling 5 ns (loop crossover <= 20 MHz)',
        'criterion': 'idac1 peak-to-peak <= 2% of its maximum over the last 50 us of a 400 us run',
        'compensated_points': len(fixed), 'compensated_settled': sum(1 for r in fixed if r.get('settled_in_last_window')),
        'outcome': 'pass' if fixed and all(r.get('settled_in_last_window') for r in fixed) else ('fail' if fixed else 'not_run'),
        'upstream_settled': [(r.get('probe'), r.get('avdd_v'), r.get('settled_in_last_window')) for r in upstream],
        'rows': [{k: r.get(k) for k in ('probe', 'corner', 'temp_c', 'vdd_v', 'netlist', 'avdd_v', 'tstop_s', 'tmax_s',
                                        'settled_in_last_window', 'last_window_pp_a', 'final_idac1_a', 'windows',
                                        'error')} for r in probes],
    }
    loops = [r for r in recs if r.get('kind') == 'bg_loopgain']
    fx = [r for r in loops if r['netlist'] == 'schematic' and not r.get('avdd_v') and not r.get('ref_sel_coarse')
          and not r.get('ref_sel_fine')]
    pm = [r.get('phase_margin_deg') for r in fx if r.get('phase_margin_deg') is not None]
    gm = [r.get('gain_margin_db') for r in fx if r.get('gain_margin_db') is not None]
    out['bandgap_loop_gain'] = {
        'method': 'AC loop gain of the bandgap-mode loop broken at the bias_amp_large + input (1 GH / 1 F break), '
                  'T = -v(vfb)/v(vfb_amp)',
        'criterion': 'phase margin >= 45 deg and gain margin >= 10 dB at every compensated point '
                     '(tt/ss/ff x 0/22/32/85 C x 3.15/3.35 V)',
        'compensated_points': len(fx),
        'phase_margin_deg_min_max': [min(pm), max(pm)] if pm else None,
        'gain_margin_db_min_max': [min(gm), max(gm)] if gm else None,
        'outcome': 'pass' if fx and len(pm) == len(fx) and min(pm) >= 45 and gm and min(gm) >= 10 else
                   ('fail' if fx else 'not_run'),
        'coarse_range_function_window': (lambda cw: {
            'points': len(cw),
            'phase_margin_deg_min_max': [min(r['phase_margin_deg'] for r in cw), max(r['phase_margin_deg'] for r in cw)]
            if cw and all(r.get('phase_margin_deg') is not None for r in cw) else None,
            'outcome': 'pass' if cw and all((r.get('phase_margin_deg') or 0) >= 45 for r in cw) else 'fail'})(
            [r for r in loops if r['netlist'] == 'schematic' and r.get('ref_sel_coarse') and not r.get('ref_sel_fine')
             and not r.get('avdd_v') and r['temp_c'] in (22, 27, 32)]),
        'coarse_range_outside_window_no_crossover': [(r['corner'], r['temp_c'], r['vdd_v'], r.get('dc_loop_gain_db'))
                                                     for r in loops if r.get('ref_sel_coarse') and not r.get('ref_sel_fine')
                                                     and r.get('unity_gain_hz') is None],
        'rows': [{k: r.get(k) for k in ('corner', 'temp_c', 'vdd_v', 'netlist', 'avdd_v', 'ref_sel_coarse', 'ref_sel_fine',
                                        'dc_loop_gain_db', 'unity_gain_hz', 'phase_margin_deg', 'gain_margin_db', 'error')}
                 for r in loops],
    }
    comp = [r for r in recs if r.get('kind') == 'bg_compliance']
    out['source_compliance'] = [{k: r.get(k) for k in ('corner', 'temp_c', 'mode', 'idac1_at_1v0_a',
                                                       'idac1_within_5pct_min_vout_v', 'idac1_within_5pct_max_vout_v',
                                                       'error')} for r in comp]
    out['unit_current_expected_by_upstream_a'] = unit_expected
    out['simulation_errors'] = errors
    return out


def summarize_bandgap(recs):
    out = {}
    trim = [r for r in recs if r.get('kind') == 'bgap_trim' and 'error' not in r]
    out['vbg_vs_trim_tt27'] = {r['trim']: r['vbg_v'] for r in sorted(trim, key=lambda r: r['trim'])}
    dc = [r for r in recs if r.get('kind') == 'bgap_dc' and 'error' not in r]
    out['standalone_ideal_bias'] = {
        'configuration': 'ideal 250 nA / 1 uA sinks on ibias1_250n / ibias2_1u (upstream conditions), trim code 8, 3.3 V',
        'rows': [{k: r.get(k) for k in ('corner', 'temp_c', 'netlist', 'vbg_v', 'supply_current_a')} for r in dc]}
    win = [r for r in dc if r['temp_c'] in (22, 27, 32) and r['netlist'] == 'schematic']
    out['standalone_ideal_bias']['window_vbg_v_min_max'] = [min(r['vbg_v'] for r in win), max(r['vbg_v'] for r in win)] if win else None
    sc = [r for r in recs if r.get('kind') == 'bgap_biasscale' and 'error' not in r]
    out['bias_current_sensitivity'] = [{k: r.get(k) for k in ('corner', 'bias_scale', 'vbg_v')} for r in sc]
    ch = [r for r in recs if r.get('kind') == 'chain_tran' and 'error' not in r]
    out['chain_function_window'] = {
        'configuration': 'biasgen sinks (bandgap_sink1 code 7, bandgap_sink2 code 3) -> bandgap (trim 8) -> vbg -> '
                         'compensated biasgen (bandgap mode, coarse, idac2 code 10) -> distribution root -> 5 banks; '
                         '100 us VDD ramp, values after a 3 ms hold',
        'criterion': 'bandgap started (1.0 V < vbg < 1.4 V, < 5 mV p-p at the end) at every window point',
        'points': len(ch), 'started': sum(1 for r in ch if r.get('started')),
        'outcome': 'pass' if ch and all(r.get('started') for r in ch) else 'fail',
        'vbg_v_min_max': [min(r['vbg_final_v'] for r in ch), max(r['vbg_final_v'] for r in ch)] if ch else None,
        'dist_out_a_min_max': [min(r['dist_out_min_a'] for r in ch), max(r['dist_out_max_a'] for r in ch)] if ch else None,
        'rows': [{k: r.get(k) for k in ('corner', 'temp_c', 'vdd_v', 'netlist', 'vbg_final_v', 'idac2_final_a',
                                        'bandgap_bias_ibias1_a', 'bandgap_bias_ibias2_a', 'dist_out_min_a',
                                        'dist_out_max_a', 'supply_current_final_a', 'vbg_settle_1pct_after_vdd90_s',
                                        'started')} for r in ch]}
    st = [r for r in recs if r.get('kind') == 'startup']
    out['startup_safe_range'] = {
        'configuration': 'biasgen + bandgap (no distribution), VDD 0 -> 3.63 V, rise 1 us / 100 us / 10 ms / 1 s, '
                         'tt 0/27/85 C, ff 0/85 C, ss 0/85 C; hold >= 3 ms (30 % of the ramp for slow ramps)',
        'criterion': 'no zero-current / stuck state: vbg ends between 1.0 and 1.4 V with < 5 mV p-p',
        'points': len(st), 'started': sum(1 for r in st if r.get('started')),
        'outcome': 'pass' if st and all(r.get('started') for r in st) else 'fail',
        'rows': [{k: r.get(k) for k in ('corner', 'temp_c', 'trise_s', 'vbg_final_v', 'idac2_final_a',
                                        'vbg_settle_1pct_after_vdd90_s', 'vbg_tail_pp_v', 'supply_current_peak_a',
                                        'started', 'error')} for r in st]}
    out['atb0_force_1v2'] = [{k: v for k, v in r.items() if k not in ('job', 'kind')}
                             for r in recs if r.get('kind') == 'chain_atb_force']
    pr = [r for r in recs if r.get('kind') == 'chain_probe']
    out['fine_step_probes'] = {
        'criterion': 'idac2 p-p <= 2 % and vbg p-p < 5 mV over the last 50 us of 600 us (5 ns step ceiling)',
        'outcome': 'pass' if pr and all(r.get('settled') for r in pr) else 'fail',
        'rows': [{k: v for k, v in r.items() if k not in ('job', 'kind')} for r in pr]}
    out['simulation_errors'] = [r['job'] for r in recs if 'error' in r]
    return out


def summarize_dist(recs, gen_dir):
    out = {'layout': {}}
    for p in sorted(glob.glob(os.path.join(gen_dir, '*-layout.json'))):
        j = json.load(open(p))
        out['layout'][j['cell']] = {k: j.get(k) for k in ('magic_drc_errors', 'klayout_drc', 'lvs_final', 'area_um2',
                                                           'width_um', 'height_um', 'gds_export', 'hashes',
                                                           'layout_image_id')}
    dc = [r for r in recs if r.get('kind') == 'dist_dc']
    win = [r for r in dc if r['trunk_enabled'] and r['outputs_enabled'] and r['island_rail'] == 'vdd'
           and r['reference'] == 'ideal' and 'error' not in r]
    ch = [r for r in dc if r['reference'] == 'biasgen' and 'error' not in r]
    off = [r for r in dc if (not r['trunk_enabled'] or not r['outputs_enabled']) and 'error' not in r]
    isl = [r for r in dc if r['island_rail'] == 'visl_off' and 'error' not in r]
    out['function_window_ideal_10uA_reference'] = {
        'criterion': 'every output (23) within 10 uA +/- 5 % (consumer at 0.95 V or NMOS diode), '
                     'tt/ss/ff x 22/32 C x 3.15/3.35 V + nominal',
        'points': len(win), 'out_min_a': min(r['out_min_a'] for r in win) if win else None,
        'out_max_a': max(r['out_max_a'] for r in win) if win else None,
        'outcome': 'pass' if win and all(9.5e-6 <= r['out_min_a'] and r['out_max_a'] <= 10.5e-6 for r in win) else 'fail',
        'netlists': sorted({r['netlist'] for r in win}),
    }
    out['chained_behind_compensated_biasgen'] = {
        'configuration': 'biasgen bandgap mode, ref_sel_coarse=1, idac2 code 10 -> pt_bias_root (ideal vbg = 1.2 V)',
        'points': len(ch), 'out_min_a': min(r['out_min_a'] for r in ch) if ch else None,
        'out_max_a': max(r['out_max_a'] for r in ch) if ch else None,
        'rows': [{k: r.get(k) for k in ('corner', 'temp_c', 'vdd_v', 'netlist', 'out_min_a', 'out_max_a',
                                        'biasgen_idac2_a', 'supply_current_a')} for r in ch],
    }
    out['disabled'] = {
        'criterion': 'output EN=0 or trunk EN=0: every output < 1 nA (0..85 C, 3.63 V)',
        'points': len(off), 'max_output_a': max(max(abs(r['out_min_a']), abs(r['out_max_a'])) for r in off) if off else None,
        'outcome': 'pass' if off and all(max(abs(r['out_min_a']), abs(r['out_max_a'])) < 1e-9 for r in off) else 'fail',
    }
    out['island_rail_off'] = {
        'criterion': 'island rail 0 V with root trunk and all EN high (NMOS diode consumers): no output current, '
                     'core supply draws only the 10 uA reference',
        'points': len(isl), 'max_output_a': max(max(abs(r['out_min_a']), abs(r['out_max_a'])) for r in isl) if isl else None,
        'max_core_supply_a': max(r['supply_current_a'] for r in isl) if isl else None,
        'outcome': 'pass' if isl and all(max(abs(r['out_min_a']), abs(r['out_max_a'])) < 1e-9 and r['supply_current_a'] < 10.5e-6
                                         for r in isl) else 'fail',
    }
    for kind, key in (('dist_compliance', 'compliance'), ('dist_atb_force', 'atb_force'), ('dist_ramp', 'supply_ramps')):
        out[key] = [{k: v for k, v in r.items() if k not in ('job', 'kind')} for r in recs if r.get('kind') == kind]
    out['simulation_errors'] = [r['job'] for r in recs if 'error' in r]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--analog-image', required=True)
    ap.add_argument('--analog-image-id', required=True)
    ap.add_argument('--avalon-rev', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    allrecs = load_results(a.work, 'results_*.json')
    por_recs = [r for r in allrecs if str(r.get('kind', r.get('job', ''))).startswith('por')]
    bg_recs = [r for r in allrecs if str(r.get('kind', r.get('job', ''))).startswith('bg_')]
    jobs = [r.get('job') for r in allrecs]
    dup = sorted({j for j in jobs if jobs.count(j) > 1})
    if dup:
        raise SystemExit('duplicate simulation records across result files: %s' % dup[:5])
    hashes = {
        'manifest/por.sha256': sha256(os.path.join(HERE, 'manifest/por.sha256')),
        'manifest/biasgen.sha256': sha256(os.path.join(HERE, 'manifest/biasgen.sha256')),
    }
    for p in sorted(glob.glob(os.path.join(HERE, 'patches/*.patch')) + glob.glob(os.path.join(HERE, 'flow/*'))
                    + glob.glob(os.path.join(HERE, 'distribution/*.py'))
                    + glob.glob(os.path.join(HERE, 'biasgen_tapeout/*'))
                    + [os.path.join(HERE, 'run_core_support.sh')]):
        if os.path.isfile(p) and not p.endswith('.pyc'):
            hashes[os.path.relpath(p, HERE)] = sha256(p)
    hashes['manifest/bandgap.sha256'] = sha256(os.path.join(HERE, 'manifest/bandgap.sha256'))
    for blk, cell in (('por', 'gf180mcu_ocd_ip__por'), ('biasgen', 'gf180mcu_ocd_ip__biasgen'),
                      ('bandgap', 'gf180mcu_ocd_ip__bandgap')):
        for sub in ('gds/%s.gds.gz' % cell, 'magic/%s.mag' % cell, 'netlist/schematic/%s.spice' % cell,
                    'xschem/%s.sch' % cell):
            hashes['%s/%s' % (blk, sub)] = sha256(os.path.join(HERE, blk, sub))
    canary_id = read(os.path.join(a.work, 'canary_image_id.txt'))
    ev = {
        'schema': 'svalbard.core_support_evidence/1',
        'reproduce': 'projects/programmable_transceiver_platform/analog/core_support/run_core_support.sh',
        'configuration': {
            'analog_image': a.analog_image, 'analog_image_id': a.analog_image_id,
            'digital_crosscheck_image': 'svalbard/librelane-gf180-canary:2026.08', 'digital_crosscheck_image_id': canary_id,
            'pdk': 'gf180mcuD (open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7 in the analog image)',
            'models': 'design.ngspice + sm141064.ngspice {typical|ff|ss} with matching res_/mimcap_/diode_ corners; ngbehavior=hsa',
            'std_cells': 'Avalon gf180mcu_as_sc_mcu7t3v3 @ ' + a.avalon_rev,
            'upstream': {'por': 'RTimothyEdwards/gf180mcu_ocd_ip__por@a6f16be7c509820f2bd50f7ac517edb58cf8a3f2 (Apache-2.0)',
                         'biasgen': 'RTimothyEdwards/gf180mcu_ocd_ip__biasgen@96a93f811a10c0b63111a5bd862e3173300802d4 (Apache-2.0)'},
            'operating_envelope': {'function': 'tt/ss/ff x 22/32 C x 3.15/3.35 V plus tt/27 C/3.3 V',
                                   'safety': '0 -> 3.63 V ramps, brownout, repeated ramps, 0..85 C',
                                   'exploratory_only': '-40/125 C, 3.0/3.6 V'},
            'single_supply_mapping': 'biasgen avdd = dvdd = ref_in = VDD, avss = dvss = 0 (die has one supply and one ground net)',
            'por_measurement': 'released = porb > VDD/2 with VDD >= 1.0 V; asserted = porb < VDD/2 with VDD >= 1.0 V',
        },
        'source_hashes_sha256': hashes,
        'clean': {blk: clean_block(a.work, blk) for blk in ('por', 'biasgen', 'biasgen_patched', 'bandgap', 'bandgap_patched')},
        'por': summarize_por(por_recs) if por_recs else 'not_run',
        'biasgen': summarize_bg(bg_recs) if bg_recs else 'not_run',
        'bandgap': summarize_bandgap([r for r in allrecs if str(r.get('kind', '')).startswith(('bgap', 'chain', 'startup'))]),
        'distribution': summarize_dist([r for r in allrecs if str(r.get('kind', '')).startswith('dist')],
                                       os.path.join(HERE, 'distribution', 'generated')),
        'excluded_coverage': [
            'Mismatch/Monte-Carlo: not run (process corners only).',
            'POR and biasgen were simulated with schematic netlists except the listed PEX points; '
            'biasgen PEX is capacitance-only (Magic R+C extraction segfaults on this layout) and uses the locally patched layout.',
            'No powered-peer or pad back-drive case: both cells are internal and have no pad connection of their own.',
            'Integration-level reset combining (POR OR RESET_N) and ATB force/sense are specified in README, not simulated here.',
            'The voltgen and class-AB buffer cells (other than the buffer inside the bandgap) are not imported.',
            'Biasgen stand-alone sims (bg_*) use an ideal 1.2 V vbg; the full reference chain with the imported bandgap is in "bandgap".',
            'Bandgap PNP corner is tied to the MOS corner (bjt_typical/ss/ff with typical/ss/ff); upstream treats it as independent.',
            'Bandgap tapeout source is the vendored upstream GDS: the analog-image re-export from the current .mag differs only on PPLUS (31/0) in the PDK PNP cells and fails KLayout PP.2 (see clean.bandgap_patched).',
            'ref_sel_fine=1 with ref_sel_coarse=0 keeps only ~25 deg phase margin after the fix and must be forbidden.',
            'Biasgen loads are ideal voltage sources (sources at 1.0 V, sinks at VDD-1.0 V), not the real island bias inputs.',
            'Substrate/ESD/latch-up behaviour beyond the compact-model diodes is not simulated.',
            'Biasgen bandgap-mode probes cover 6 corner/temperature/supply points plus 5 V avdd and the C-only PEX; '
            'loop gain covers tt/ss/ff x 0/22/32/85 C x 3.15/3.35 V; mismatch is not covered.',
            'Bias distribution consumers are ideal 0.95 V sources or NMOS diodes, not the blocks\' extracted inputs; '
            'trunk wire RC across the floorplan is not modelled.',
            'POR safety sweeps use the schematic netlist; PEX was run at the 13 function-window points only.',
            'GDS used for tapeout must be regenerated from the (patched) Magic view; the vendored biasgen GDS predates later layout edits.',
        ],
    }
    # every extracted-netlist simulation must have used the PEX netlist reported under "clean"
    pex_ok = {}
    for blk, src in (('por', 'por'), ('biasgen_patched', 'bg_'), ('bandgap', ('bgap', 'chain'))):
        want = (ev['clean'][blk].get('pex_netlist') or {}).get('sha256')
        used = {r.get('pex_netlist_sha256') for r in allrecs
                if r.get('netlist') == 'pex' and str(r.get('kind', '')).startswith(src)}
        nohash = sum(1 for r in allrecs if r.get('netlist') == 'pex' and str(r.get('kind', '')).startswith(src)
                     and not r.get('pex_netlist_sha256'))
        hashed = {u for u in used if u}
        pex_ok[blk] = {'clean_pex_sha256': want, 'simulated_pex_sha256': sorted(hashed),
                       'records_without_hash': nohash,
                       'consistent': bool(hashed) and hashed == {want}}
    ev['pex_simulation_consistency'] = pex_ok
    # LVS qualification of the two tapeout sources.  Every listed comparison
    # must be a strict match (lvs_result); otherwise the evidence is written
    # with status fail and this script exits non-zero.
    required = {
        'biasgen_patched': {
            'lvs_magic_hierarchical_common_ground': 'Magic hierarchical extraction, avss=dvss in both netlists',
            'lvs_gds_flat': 'flat extraction of the tapeout GDS, separate avss/dvss',
            'lvs_gds_flat_common_ground': 'flat extraction of the tapeout GDS, avss=dvss',
        },
        'bandgap': {
            'lvs_magic_hierarchical_pnp_alias': 'Magic hierarchical extraction, PNP recognition alias',
            'lvs_gds_flat_pnp_alias': 'flat extraction of the vendored tapeout GDS, PNP recognition alias',
        },
    }
    rows, ok = [], True
    for blk, checks in required.items():
        for key, what in checks.items():
            r = ev['clean'][blk].get(key) or {'match': False, 'final': 'missing'}
            rows.append({'block': blk, 'comparison': key, 'what': what, 'match': bool(r.get('match')),
                         'final': r.get('final'), 'failure_count': r.get('failure_count')})
            ok &= bool(r.get('match'))
    ev['lvs_qualification'] = {
        'status': 'pass' if ok else 'fail',
        'rule': 'strict netgen reading (summarize.lvs_result): unique final match, no property errors, no pin '
                'mismatches, no unresolved non-match; only auto-named disconnected extraction ports and '
                'netgen-flattened subcell non-matches are tolerated and are listed per comparison',
        'required': rows,
        'diagnostic_not_required': {
            'biasgen_patched.lvs_magic_hierarchical': 'expected to fail: Magic hierarchical extraction joins avss and '
                'dvss through the shared p-substrate (both tap it), so the layout has one ground net where the '
                'schematic has two; the idac1/idac2 and sink pin swaps netgen then reports are symmetry fallout of '
                'that non-match.  The die binds both to VSS (integration/core_bias.py), which is what the '
                'common-ground comparisons check.',
            'bandgap.lvs_magic_hierarchical / lvs_gds_flat': 'expected to fail: this PDK Magic tech names the 5x5 PNP '
                'pnp_10p00x00p42; the _pnp_alias comparisons map that name back',
        },
    }
    with open(os.path.join(a.out, 'core_support_evidence.json'), 'w') as f:
        json.dump(ev, f, indent=1, sort_keys=False)
        f.write('\n')
    print('wrote', os.path.join(a.out, 'core_support_evidence.json'))
    print('lvs_qualification', ev['lvs_qualification']['status'])
    if ev['lvs_qualification']['status'] != 'pass':
        raise SystemExit('LVS qualification failed: %s' % [r for r in rows if not r['match']])


if __name__ == '__main__':
    main()
