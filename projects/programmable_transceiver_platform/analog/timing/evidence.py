"""Assemble generated/<block>-evidence.json from scratch/timing/<block>/results.json.

States are derived from recorded run output only:
  clean      pass iff DRC==0, LVS unique and every nominal extracted case passes
             its basic-function check (secondary stretch cases are reported in
             performance_vs_target and do not gate).
  safe       pass iff every reset-default case draws < 1 uA average (excluding
             the pll_ring IBIAS input current, which is the bias generator's) and the
             island-off pad case (diff_clk_rx) stays < 1 uA.
  observable pass iff the block exposes the listed status/ATB/clock-observation
             points (structural) -- registered mapping is open until the
             register map exists, so the state is 'open' when it depends on it.
  fallback   records the route; the route itself is exercised by the other
             blocks' evidence (no state is claimed beyond 'open' unless the
             bypass hardware is in this block and was simulated).
"""
import argparse
import json
from pathlib import Path

import timing_flow as tf

# Gating = the block's basic function at a moderate nominal frequency; the
# GHz-rate cases are performance data (performance_vs_target), not gates.
GATING = dict(prescale=['nom_2g5_d16', 'nom_240m_d2'], pll_ring=['closed_480m', 'closed_625m', 'closed_810m', 'closed_hf125m_n4', 'closed_hf156m_n4'], lo_ext=['nom_ext_sin_2vpp_pad', 'nom_int'],
              diff_clk_rx=['nom_diff_100m_500mv', 'nom_se_1g_600mv', 'data_0g5_500mv', 'data_1g_500mv', 'data_1g6_300mv',
                           'data_1g6_500mv', 'data_1g6_800mv', 'data_pre128_0g5_300mv'],
              clk_obs=['nom'],
              clockmux=['nom', 'nom_mode_rf', 'nom_mode_wired'],
              wordclk=['nom_480m_d5', 'nom_480m_d10', 'nom_480m_d20', 'nom_810m_d5', 'nom_810m_d10', 'nom_810m_d20'],
              vco_replica=['nom_vc1.5', 'nom_vc2.1', 'nom_vc3.3'])
AREA_CEILING = dict(wordclk=None, prescale=None, pll_ring=None, lo_ext=None, diff_clk_rx=180000, aosc=20000, clockmux=80000,
                    clk_obs=None, ring_osc=None, vco_replica=None)
CEILING_SOURCE = dict(lo_ext='booked against the quadrature 150k ceiling (spec/consolidation-pass.md P3-1)',
                      diff_clk_rx='analog-architecture.json blocks.refinput (per instance)',
                      clk_obs='debug structure; 0.41 mm2 shared reserve',
                      ring_osc='characterization structure; 0.41 mm2 shared reserve',
                      vco_replica='characterization structure; 0.41 mm2 shared reserve')
OBS = dict(
    prescale=dict(atb_taps=[], status_bits=[], clock_obs=['CK_OUT -> WCLK_OBS input']),
    wordclk=dict(atb_taps=[], status_bits=[], clock_obs=['WORD_CLK -> WCLK_OBS input']),
    pll_ring=dict(atb_taps=['ATB_VCTRL'], status_bits=['LOCK'], clock_obs=['FBCK', 'PH0..PH7']),
    lo_ext=dict(atb_taps=['ATB_VB (mixer LO bias, sense/force)'], status_bits=[], clock_obs=['none (2.45 GHz analog node; observe via the mixers)']),
    diff_clk_rx=dict(atb_taps=['ATB_DET (clock-present detector node A)'], status_bits=['PRESENT'],
                     clock_obs=['OUTP (to clockmux and a CLK_OBS input)']),
    clk_obs=dict(atb_taps=[], status_bits=[], clock_obs=['is the observation path itself (OUT -> CLK_OBS pad)']),
    ring_osc=dict(atb_taps=[], status_bits=[], clock_obs=['OUT -> CLK_OBS input']),
    aosc=dict(atb_taps=['ATB_X (timing capacitor)'], status_bits=[], clock_obs=['CLK -> CLK_OBS input']),
    clockmux=dict(atb_taps=[], status_bits=[], clock_obs=['WIRE, PREF, CONV_CLK, HOST_CLK -> CLK_OBS inputs']),
    vco_replica=dict(atb_taps=['VCTRL (force input)', 'ATB_VTAIL (ring bottom rail)'], status_bits=[], clock_obs=['OUT (VCO/16) -> CLK_OBS input']))
FALLBACK = dict(
    prescale=dict(routes=[], notes='Front end for rtl/pt_clocktree_slow.sv.'),
    wordclk=dict(routes=['external line clock: CK may be the WCLK_IN path from clockmux WIRE'], notes='Shared TX/RX word divider (P3-6).'),
    pll_ring=dict(routes=['wire_clk_external_ref', 'wire_clk_wclk_in'], notes='Wired PLL with the compact 8-phase ring.'),
    lo_ext=dict(routes=['rf_lo_external_ref (revised): passive external I/Q LO on REF_IN/AUX_CLK onto the mixer gates'], notes='This block is the RF qualification baseline route itself.'),
    diff_clk_rx=dict(routes=['rf_lo_aux_clk: AUX_CLK_P/N into a second, independent pt_diff_clk_rx instance (aux_clk_rx) and clockmux RS_AUX/WS_AUX/PS_AUX'],
                     notes='One design, separate instances: refinput (REF_IN), aux_clk_rx (AUX_CLK), wired WCLK_IN and WTX_EXT receivers.'),
    clockmux=dict(routes=['clk_stop_and_external: every domain defaults to stopped and can take REF_IN or AUX_CLK (wired also WCLK_IN) with the PLL off',
                          'host_follow (P3-3): PREF=H2D_CLK -> pll_ring -> prescale -> HF -> CONV_CLK / HOST_CLK, for passive-LO RF where REF_IN/AUX_CLK carry the LO'],
                  notes='Selections are one-hot inputs; all-zero is stopped.'),
    aosc=dict(routes=[], notes='Core block: fallback waived; self-contained RC oscillator (no bias input).'),
    clk_obs=dict(routes=[], notes='Debug cell.'), ring_osc=dict(routes=[], notes='Characterization structure.'),
    vco_replica=dict(routes=[], notes='Characterization structure.'))


def observable_state(block, nominal):
    # spec/debug-controls.json obs_status has ref_present and pll_lock; ATB
    # code 30 is pll_vctrl.  Claim pass only with a simulated observation.
    if block == 'diff_clk_rx':
        return 'pass' if any((r.get('present') or 0) > 3.0 and r.get('pass') for r in nominal) else 'open'
    if block == 'pll_ring':
        return 'pass' if any((r.get('lock_end_v') or 0) > 3.0 and r.get('pass') for r in nominal) else 'open'
    return 'open'


BYPASS_LOADING = dict(
    clockmux='Estimate from device sizes, not extracted: each source drives one NAND2 input (2u/2u, ~6 fF gate) per domain that lists it plus routing; REF loads 4 domains (~25 fF + wiring), AUX 3, H2D 1, HF 2.',
    diff_clk_rx='Disabled pad loading: stage-1 gate (6u/0.28 PMOS + 3u/0.28 NMOS, ~13 fF) + NMOS switch junction + ESD (pads family).')


def assemble(block):
    res_path = tf.SCRATCH / block / 'results.json'
    if not res_path.exists():
        return None
    res = json.loads(res_path.read_text())
    lay = res.get('layout', {})
    nominal = res.get('nominal', [])
    gating_names = GATING.get(block)
    gate = [r for r in nominal if gating_names is None or Path(r.get('deck', '')).stem in gating_names]
    def clean_r(r):
        r = dict(r)
        if block == 'clockmux' and 'rf_pll_hz' in r:
            # re-derive pass with the final criterion (stopped outputs must not
            # cross VDD/3); the raw values are unchanged
            v = r.get('vdd_v', 3.3)
            freqs = ('rf_pll_hz', 'rf_ref_hz', 'rf_aux_hz', 'wire_wck_hz', 'pll_ref_hz',
                     'wire_sample_ref_hz', 'conv_sample_aux_hz')
            want = dict(rf_ref_hz=1e9, rf_aux_hz=0.5e9, wire_wck_hz=0.4e9, pll_ref_hz=1e9,
                        wire_sample_ref_hz=1e9, conv_sample_aux_hz=0.5e9)
            fp = {'nom': 1e9, 'nom_pll2g': 2e9, 'nom_pll2g5': 2.5e9}.get(Path(r.get('deck', '')).stem.split('_tt')[0].split('_ss')[0].split('_ff')[0], 1e9)
            want['rf_pll_hz'] = fp
            ok = all(r.get(k) and abs(r[k] / f - 1) < 0.01 for k, f in want.items())
            ok = ok and (r.get('rf_p_max_during_stop_gap_v') or 9) < v / 3 and (r.get('stopped_rf_p_max_v') or 9) < v / 3 \
                and (r.get('stopped_rf_n_min_v') or 0) > 2 * v / 3
            r['pass'] = bool(ok)
        for k in ('duty', 'duty_i', 'duty_q'):
            if isinstance(r.get(k), (int, float)) and not (0 < r[k] < 1):
                r[k] = None  # measurement window artifact, not a duty cycle
        return r
    nominal = [clean_r(r) for r in nominal]
    gate = [clean_r(r) for r in gate]
    nominal_ok = bool(gate) and all(r.get('pass') for r in gate)
    kl = lay.get('klayout')
    klp = tf.SCRATCH / block / 'layout' / 'klayout.json'
    if kl is None and klp.exists():
        kl = json.loads(klp.read_text())
    # Required: the tapeout precheck's KLayout decks (DRC + antenna) on the published GDS
    # (verification/kl_block_drc.py --publish -> generated/<block>-kldrc.json, current GDS hash).
    pre_p = tf.GENERATED / f'{block}-kldrc.json'
    pre = json.loads(pre_p.read_text()) if pre_p.exists() else None
    gds_p = tf.GENERATED / f'{block}.gds'
    pre_ok = bool(pre and pre.get('clean') and gds_p.exists() and 'sha256:' + pre.get('gds_sha256', '') == tf.sha(gds_p))
    drc_ok = lay.get('drc_errors') == 0 and bool(kl and kl.get('ran') and kl.get('violations') == 0) and pre_ok
    lvs_ok = bool(lay.get('lvs', {}).get('unique_match'))
    clean_state = 'pass' if (drc_ok and lvs_ok and nominal_ok) else ('fail' if lay else 'open')
    safe = res.get('safe', [])

    def safe_ok(c):
        if 'i_pad_inp_na' in c:
            return abs(c['i_pad_inp_na']) < 1000 and abs(c['i_pad_inn_na']) < 1000
        i = c.get('i_vdd_avg_ua')
        if i is None:
            return False
        if block == 'pll_ring':
            i -= 10.0  # the 10 uA IBIAS source is drawn from the same test supply
        return abs(i) < 1.0
    safe_state = 'pass' if safe and all(safe_ok(c) for c in safe) else ('fail' if safe else 'open')
    srcs = {p.name: tf.sha(p) for p in [tf.HERE / f'{block}.spice', tf.HERE / 'timing_cells.spice',
                                        tf.HERE / 'layout_engine.py', tf.HERE / 'netlist.py', tf.HERE / 'run_timing.py',
                                        tf.HERE / 'timing_flow.py']}
    if block == 'pll_ring':
        srcs['pll.spice'] = tf.sha(tf.HERE / 'pll.spice')
    for f in sorted((tf.GENERATED / 'fast').glob('*.spice')):
        if f.name.endswith('.ext.spice') or f.name.endswith('.lvs.spice'):
            continue
        if f.stem in (tf.HERE / f'{block}.spice').read_text():
            srcs['fast/' + f.name] = tf.sha(f)
    gen = {p.name: tf.sha(p) for p in tf.GENERATED.glob(f'{block}.*') if p.is_file()}
    area = lay.get('area_um2')
    ceil = AREA_CEILING.get(block)
    perf = []
    for r in nominal:
        perf.append(dict(kind='nominal_extracted', **r))
    for r in res.get('corners', []):
        perf.append(dict(kind='corner_extracted', **clean_r(r)))
    if 'schematic_closed_loop' in res:
        perf.append(dict(kind='closed_loop_schematic', **res['schematic_closed_loop']))
    perf.append(dict(kind='area', area_um2=area, ceiling_um2=ceil, ceiling_source=CEILING_SOURCE.get(block, 'analog-architecture.json blocks.' + block),
                     fits=(area <= ceil) if (area and ceil) else None))
    rec = dict(
        block=block,
        source_hashes=srcs,
        generated_hashes=gen,
        images=dict(analog=tf.ANALOG_IMAGE_ID, analog_ref=tf.ANALOG_IMAGE,
                    digital=tf.image_id(tf.DIGITAL_IMAGE), digital_ref=tf.DIGITAL_IMAGE),
        pdk='gf180mcuD (digital image /pdk/gf180mcuD for Magic/Netgen; analog image /foss/pdks/gf180mcuD models for ngspice)',
        tests=dict(
            safe=dict(state=safe_state, cases=safe,
                      notes='Reset-default = every control input 0; clock/pad inputs toggling. Includes 3.63 V at 85 C (ff) and 0 C (ss).'),
            clean=dict(state=clean_state,
                       drc=dict(errors=lay.get('drc_errors'), tool='Magic 8.3.623 drc(full)', report=f'generated/{block}-drc.txt',
                                klayout=kl, gds_export='analog image Magic 8.3.678, cif ostyle gdsii',
                                klayout_precheck=dict(required=True, ok=pre_ok, record=f'generated/{block}-kldrc.json',
                                                      decks={k: v.get('total') for k, v in (pre or {}).get('decks', {}).items()})),
                       lvs=dict(unique_match=lvs_ok, summary=lay.get('lvs', {}).get('summary'), tool='Netgen 1.5.316',
                                report=f'generated/{block}-lvs.txt'),
                       extracted_nominal=dict(gating_cases=[Path(r.get('deck', '')).stem for r in gate],
                                              all_pass=nominal_ok, results=gate),
                       layout=dict(size_um=lay.get('size_um'), area_um2=area, devices=lay.get('devices'),
                                   gds=f'generated/{block}.gds', mag=f'generated/{block}.mag',
                                   extracted=f'generated/{block}.ext.spice')),
            observable=dict(state=observable_state(block, nominal), **OBS[block],
                            notes='Points exist as ports; register-file / test-bus / CLK_OBS mux codes are assigned at integration (register map not yet published).'),
            fallback=dict(state='waived_core' if block == 'aosc' else 'open', bypass_loading_fF=None,
                          bypass_loading_note=BYPASS_LOADING.get(block), **FALLBACK[block])),
        performance_vs_target=perf,
        excluded_coverage=res.get('excluded', []))
    return tf.write_evidence(block, rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blocks', default='diff_clk_rx,clk_obs,ring_osc,aosc,clockmux,vco_replica,lo_ext,pll_ring,prescale,wordclk')
    a = ap.parse_args()
    for b in a.blocks.split(','):
        p = assemble(b)
        print(b, p)
    readme = tf.HERE / 'README.md'
    text = readme.read_text()
    start, end = '<!-- results:start -->', '<!-- results:end -->'
    if start in text and end in text:
        table = summary_table('diff_clk_rx,clk_obs,ring_osc,aosc,clockmux,vco_replica,lo_ext,pll_ring,prescale,wordclk'.split(','))
        text = text[:text.index(start) + len(start)] + '\n' + table + '\n' + text[text.index(end):]
        readme.write_text(text)


def summary_table(blocks):
    """Markdown rows: block, area/ceiling, DRC, LVS, gating cases, safe max current."""
    rows = ['| Block | Devices | Area µm² (ceiling) | DRC | LVS | Extracted nominal (gating) | Safe (reset-default) | clean |',
            '| --- | ---: | ---: | ---: | --- | --- | --- | --- |']
    for b in blocks:
        p = tf.GENERATED / f'{b}-evidence.json'
        if not p.exists():
            rows.append(f'| {b} | – | – | – | – | not run | – | open |')
            continue
        e = json.loads(p.read_text())
        c = e['tests']['clean']
        lay = c['layout']
        g = c['extracted_nominal']
        gtxt = ', '.join(f"{n}: {'pass' if r.get('pass') else 'FAIL'}" for n, r in zip(g['gating_cases'], g['results'])) or 'none'
        s = e['tests']['safe']
        imax = max((abs(x.get('i_vdd_avg_ua') or 0) for x in s['cases'] if 'i_vdd_avg_ua' in x), default=None)
        ceil = next((x for x in e['performance_vs_target'] if x.get('kind') == 'area'), {})
        rows.append(f"| `{b}` | {lay.get('devices')} | {lay.get('area_um2'):,.0f} ({ceil.get('ceiling_um2') or 'reserve'}) | "
                    f"{c['drc']['errors']} | {'unique' if c['lvs']['unique_match'] else 'FAIL'} | {gtxt} | "
                    f"{s['state']} (max avg {imax:.3g} µA) | {c['state']} |" if imax is not None else
                    f"| `{b}` | {lay.get('devices')} | {lay.get('area_um2')} | {c['drc']['errors']} | {c['lvs']['unique_match']} | {gtxt} | {s['state']} | {c['state']} |")
    return '\n'.join(rows)


if __name__ == '__main__':
    main()
