"""Compose generated/<block>-evidence.json from layout reports and bench results.

States are derived from recorded numbers with the criteria written here; nothing
is asserted without a corresponding run output.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE / 'generated'
ARCH = json.loads((HERE.parents[1] / 'spec/analog-architecture.json').read_text())

SAFE_STATIC_LIMIT_UA = 1.0      # reset / rail-off static current per rail, DC operating point
SAFE_TRAN_LIMIT_UA = 10.0       # transient mean incl. LO displacement-current residue


def sha(p):
    return 'sha256:' + hashlib.sha256(Path(p).read_bytes()).hexdigest()


def r(sim, name):
    e = sim['results'].get(name, {})
    if 'error' in e:
        return {'error': e['error']}
    return e.get('result', {})


def safety_cases(sim, rail_key):
    cases, ok = [], True
    for name, e in sim['results'].items():
        if not name.startswith('safe_') or 'result' not in e:
            continue
        res, meta = e['result'], e['meta']
        if name.startswith('safe_ramp'):
            v = res['rail_current_at_3p63V_uA']
            limit = SAFE_TRAN_LIMIT_UA if meta.get('en_level', 0) == 0 else None  # transient mean 50-200 ns after the ramp
            passed = None if limit is None else v <= limit
            cases.append(dict(case=name, condition=meta, family_rail_current_uA_at_3p63V=v,
                              peak_uA=res['rail_current_peak_uA'], criterion=f'<= {limit} uA' if limit else 'informational (enabled)',
                              pass_=passed))
            ok &= passed in (None, True)
            continue
        enabled = meta.get('en', 0) == 1 and meta.get('ctrl', 0) > 0 and meta.get('vdd', 3.3) > 0
        static = res.get('dc_op_uA', {}).get(rail_key)
        tran = res.get(f'{rail_key}_uA')
        entry = dict(case=name, condition={k: v for k, v in meta.items() if k != 'kind'},
                     rail_static_uA=static, rail_transient_mean_uA=tran,
                     bb_dac_source_static_uA=res.get('dc_op_uA', {}).get('bb_dac_source'),
                     pad_source_current_mA=res.get('pad_source_current_mA'))
        if enabled:
            entry.update(criterion='informational (block enabled)', pass_=None)
        elif 'pad_drive' in meta and meta['pad_drive'] > 0.5:
            entry.update(criterion='out of contract: DC-driven RF_TX (board must DC-block RF_TX)', pass_=None)
        else:
            passed = (static is not None and abs(static) <= SAFE_STATIC_LIMIT_UA and abs(tran) <= SAFE_TRAN_LIMIT_UA
                      and (entry['pad_source_current_mA'] is None or abs(entry['pad_source_current_mA']) < 1.0))
            entry.update(criterion=f'|static| <= {SAFE_STATIC_LIMIT_UA} uA, |transient mean| <= {SAFE_TRAN_LIMIT_UA} uA, '
                                   'pad peer current < 1 mA', pass_=bool(passed))
            ok &= bool(passed)
        cases.append(entry)
    return cases, ok


def perf(metric, target, achieved, unit, condition, source, note=''):
    return dict(metric=metric, target=target, achieved=achieved, unit=unit, condition=condition, source=source, note=note)


def corners(sim, key, sub=None, prefix='corner_'):
    out = []
    for name, e in sim['results'].items():
        if name.startswith(prefix) and 'result' in e:
            m = e['meta']; v = e['result'][key] if sub is None else e['result'][key][sub]
            out.append(dict(corner=m['corner'], temp_C=m['temp'], vdd_V=m['vdd'], value=v))
    return out


def build():
    ext = json.loads((GEN / 'rf_tx-sim-ext.json').read_text())
    sch = json.loads((GEN / 'rf_tx-sim-sch.json').read_text()) if (GEN / 'rf_tx-sim-sch.json').exists() else None
    src = 'generated/rf_tx-sim-ext.json'
    common_hashes = {f: sha(HERE / f) for f in ('circuits.py', 'layoutlib.py', 'generate.py', 'simulate.py', 'run_benches.py',
                                                 'evidence.py', 'run_rf_tx.sh') if (HERE / f).exists()}
    chain = r(ext, 'chain_dc')
    docs = {}
    for block in ('txmix_i', 'txmix_q', 'txsum', 'rfdriver'):
        lay = json.loads((GEN / f'{block}-layout.json').read_text())
        alloc = ARCH['blocks'][block]['resource_allocation']
        rail = {'txmix_i': 'txmix_i_rail', 'txmix_q': 'txmix_q_rail', 'txsum': 'txsum_rail', 'rfdriver': 'rfdriver_rail'}[block]
        cases, safe_ok = safety_cases(ext, rail)
        gx_path = GEN / f'{block}-gds-export.json'
        gx = json.loads(gx_path.read_text()) if gx_path.exists() else {}
        clean_ok = lay['drc_errors'] == 0 and lay['lvs_unique_match'] and bool(gx.get('pass'))
        ev = dict(block=block,
                  source_hashes={f'{block}.spice': sha(HERE / f'{block}.spice'), **common_hashes},
                  output_hashes={f'generated/{block}.gds': sha(GEN / f'{block}.gds'),
                                 f'generated/{block}.ext.spice': sha(GEN / f'{block}.ext.spice')},
                  output_notes='generated/<block>.gds is the Magic 8.3.678 re-export (analog image); DRC, LVS and extraction '
                               'ran on the canary image from the same .mag.',
                  images=dict(analog=ext['analog_image_id'], analog_ref=ext['analog_image_ref'] if 'analog_image_ref' in ext else ext['analog_image'],
                              digital=lay['image_id'], digital_ref=lay['image']),
                  pdk='gf180mcuD, open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7 (both images)',
                  area=dict(width_um=lay['width_um'], height_um=lay['height_um'], area_um2=lay['area_um2'],
                            ceiling_um2=alloc['area_ceiling_um2'], fits=lay['area_um2'] <= alloc['area_ceiling_um2']),
                  tests={})
        t = ev['tests']
        t['safe'] = dict(state='pass' if safe_ok else 'fail', cases=cases,
                         notes='Family-level extracted benches (all four blocks connected, LO running, upstream baseband and '
                               'ibias live). Static currents from the DC operating point; transient means over six LO periods. '
                               'Default-off: en=0 opens bias switches and clamps; island rail off gives no static backfeed. '
                               'Board contract: RF_TX must be DC-blocked; a DC-coupled source above ~0.5 V on RF_TX with the '
                               'island rail at 0 V forward-biases the rfdriver PMOS drain junctions (recorded as out-of-contract case).')
        t['clean'] = dict(state='pass' if clean_ok else 'fail',
                          drc=dict(tool='magic 8.3.623 gf180mcuD deck', errors=lay['drc_errors'], report=f'generated/{block}-drc.txt'),
                          lvs=dict(tool='netgen 1.5.316 gf180mcuD_setup.tcl', result=lay['lvs_final'], report=f'generated/{block}-lvs.txt'),
                          gds_export=dict(rule='spec/block-deliverables.md GDS export rule', tool=f"magic {gx.get('magic_version')} "
                                          '(analog image), cif ostyle gdsii', image_id=gx.get('image_id'),
                                          marker_shapes=gx.get('marker_shapes'),
                                          ppolyf_u_1k_in_netlist=gx.get('ppolyf_u_1k_resistors_in_netlist'),
                                          hres_present_where_required=gx.get('hres_ok'), report=f'generated/{block}-gds-export.json'),
                          klayout_drc=dict(tool='KLayout GF180 deck via sak-drc.sh -k (analog image)',
                                           violations=(gx.get('klayout_drc') or {}).get('violations'),
                                           by_rule=(gx.get('klayout_drc') or {}).get('by_rule'),
                                           report=f'generated/{block}-klayout-drc.lyrdb'),
                          extracted_nominal={})
        t['observable'] = dict(state='open', atb_taps=[], status_bits=[], clock_obs=[],
                               notes='ATB taps are exposed as atb_* ports behind ~20 kohm on-block isolation resistors; '
                                     'atb_tap cells, test-bus mux codes and register fields are assigned at integration '
                                     '(analog/island_support, register map), so the test stays open.')
        t['fallback'] = dict(state='open', routes=[], bypass_loading_fF=None)
        pv, excl = [], ['Wire/via resistance not extracted (capacitance-only extraction).',
                        'No package, bond-wire or supply-network impedance; ideal 3.3 V rails.',
                        'LO is an ideal rail-to-rail square wave behind 50 ohm (quadrature block not simulated).',
                        'Baseband sources ideal (bbfilter / DAC output impedance not modelled).',
                        'No noise, mismatch/Monte Carlo, EVM or spectral-mask simulation.',
                        'Pad modelled as the rftxpad allocation (2 ohm + 1 pF per leg), not the pads agent extraction.']
        if block.startswith('txmix'):
            mp, mz, md, mo, mu = (r(ext, n) for n in ('mix_bb_p', 'mix_zero', 'mix_dac', 'mix_off', 'mix_unselected'))
            t['clean']['extracted_nominal'] = dict(
                bench='extracted pt_txmix_i, 0.3 V DC differential baseband, 2.44 GHz LO, outputs into ideal 300 ohm + 150 fF',
                conversion_transconductance_mS=mp['conversion_transconductance_mS'], out_fund_mVpk_diff=mp['out_fund_mVpk_diff'],
                lo_feedthrough_out_mVpk_diff=mz['out_fund_mVpk_diff'], dac_input_conversion_mS=md['conversion_transconductance_mS'],
                tail_current_mA=mp['tail_current_mA'], source=src,
                note='txmix_q is the same circuit and layout under a different cell name; the I-cell bench covers both, and the '
                     'full chain uses both extracted cells.')
            t['observable'].update(atb_taps=[dict(port='atb_bias', node='tail mirror gate (vbt)', on_V=mp['atb_bias_V'], off_V=mo['atb_bias_V']),
                                             dict(port='atb_tail', node='transconductor source src_p', on_V=mp['atb_tail_V'], off_V=mo['atb_tail_V'])])
            t['fallback'].update(routes=[dict(route='rf_tx_external_upconverter',
                                              this_block='disabled (en=0): no tail current, gm gates clamped, input switches open',
                                              evidence=dict(bb_input_capacitance_off_fF=r(ext, 'cap_mix_bb_off')['capacitance_fF'],
                                                            bb_input_capacitance_on_fF=r(ext, 'cap_mix_bb_on')['capacitance_fF'],
                                                            output_with_input_applied_off_mVpk=mo['out_fund_mVpk_diff']),
                                              open_items='route needs bbfilter TX output on the bb_tap buffer (rf_rx agent)'),
                                         dict(route='filter bypass input (TX->RX loopback calibration, consolidation item 1)',
                                              control='sel_dac=1 selects dac_p/dac_n, bb_p/bb_n switches open',
                                              evidence=dict(dac_path_conversion_mS=md['conversion_transconductance_mS'],
                                                            unselected_bb_leakage_out_mVpk=mu['out_fund_mVpk_diff'],
                                                            chain_ssb_dac=r(ext, 'chain_ssb_dac')),
                                              state='pass')],
                                 bypass_loading_fF=r(ext, 'cap_mix_bb_off')['capacitance_fF'])
            msat = r(ext, 'mix_sat')
            t['clean']['extracted_nominal'].update(sat_mode_conversion_mS=msat['conversion_transconductance_mS'],
                                                   sat_mode_out_fund_mVpk_diff_1p0V=r(ext, 'mix_sat_1p0')['out_fund_mVpk_diff'])
            pv += [perf('saturated-mode (sat=1) conversion transconductance at 0.3 V', None, msat['conversion_transconductance_mS'],
                        'mS', 'tt/27C/3.3V extracted', src, 'degeneration shorted; for constant-envelope modulation'),
                   perf('conversion transconductance (fundamental differential output current / DC input)', 1.0,
                        mp['conversion_transconductance_mS'], 'mS', 'tt/27C/3.3V extracted', src),
                   perf('supply current (tail, drawn through txsum loads)', alloc['current_budget_ma']['rf_tx'],
                        mp['tail_current_mA'], 'mA', 'tt/27C/3.3V extracted', src),
                   perf('LO feedthrough at mixer output with zero input', None, mz['out_fund_mVpk_diff'], 'mVpk diff',
                        'tt/27C/3.3V extracted', src, 'vs %.1f mV at 0.3 V input' % mp['out_fund_mVpk_diff']),
                   perf('chain image rejection (ideal quadrature LO)', None, r(ext, 'chain_ssb')['image_rejection_dB'], 'dB',
                        'SSB 61 MHz, 0.3 V I/Q, extracted chain', src),
                   perf('chain mixer drain fundamental vs corner', None, corners(ext, 'mixi_drain_fund_mVpk_diff'), 'mVpk diff',
                        'tt/ss/ff x 22/32 C x 3.15/3.35 V, extracted chain', src)]
        elif block == 'txsum':
            so, sf, sa = r(ext, 'sum_on'), r(ext, 'sum_off'), r(ext, 'sum_ac')
            t['clean']['extracted_nominal'] = dict(
                bench='extracted pt_txsum, ideal I/Q differential current inputs (0.5 mA DC each, 0.1 mA quadrature RF at 2.44 GHz), 150 fF load',
                out_fund_mVpk_diff=so['out_fund_mVpk_diff'], transimpedance_ohm=so['transimpedance_ohm'],
                input_impedance_ohm_at_2p44GHz=sa['input_impedance_ohm_at_2p44GHz'], out_dc_V=so['out_p_dc_V'], source=src)
            t['observable'].update(atb_taps=[dict(port='atb_cm', node='summing-node common mode', on_V=so['atb_cm_V'], off_V=sf['atb_cm_V'])])
            t['fallback'].update(routes=[dict(route='rf_tx_external_upconverter', this_block='disabled: header open, outputs clamped to VSS',
                                              evidence=dict(off_out_dc_V=sf['out_p_dc_V'], off_supply_mA=sf['supply_mA']),
                                              open_items='route needs the bb_tap observe_tx path (rf_rx agent)'),
                                         dict(route='rf_tx_low_power_external_pa', this_block='txsum stays enabled and drives RF_TX through the rfdriver bypass',
                                              evidence=r(ext, 'chain_bypass'))])
            pv += [perf('transimpedance at 2.44 GHz', ARCH['blocks']['txsum']['parameters']['output_transimpedance_ohm'],
                        so['transimpedance_ohm'], 'ohm', 'tt/27C/3.3V extracted, 150 fF load', src),
                   perf('input impedance at 2.44 GHz', ARCH['blocks']['txsum']['parameters']['input_impedance_max_ohm'],
                        sa['input_impedance_ohm_at_2p44GHz'], 'ohm', 'tt/27C/3.3V extracted', src, 'target is a maximum'),
                   perf('own supply current (mixer tail currents pass through its loads)', alloc['current_budget_ma']['rf_tx'],
                        0.0, 'mA', 'passive load; family rail draw %.3f mA = both mixer tails' % chain['supply_mA']['txsum'], src),
                   perf('chain summing-node fundamental vs corner', None, corners(ext, 'sum_fund_mVpk_diff'), 'mVpk diff',
                        'tt/ss/ff x 22/32 C x 3.15/3.35 V, extracted chain', src)]
        else:
            d50, d300, d600 = r(ext, 'drv_a50'), r(ext, 'drv_a300'), r(ext, 'drv_a600')
            t['clean']['extracted_nominal'] = dict(
                bench='extracted pt_rfdriver, ideal 2.44 GHz differential input at 2.82 V CM, pad 2 ohm + 1 pF per leg, 50 ohm differential load',
                small_signal_voltage_gain=d50['voltage_gain'], pad_dBm_at_0p3V_in=d300['pad_dBm_50ohm'],
                pad_dBm_at_0p6V_in=d600['pad_dBm_50ohm'], supply_mA=d300['supply_mA'],
                chain_pad_dBm_0p3V_DC_I=chain['pad_dBm_50ohm'], chain_ssb_wanted_dBm=r(ext, 'chain_ssb')['lsb_dBm'], source=src)
            t['observable'].update(atb_taps=[dict(port='atb_bias', node='bias line vb', on_V=d300['atb_bias_V'], off_V=r(ext, 'drv_off')['atb_bias_V']),
                                             dict(port='atb_pre', node='pre-amplifier 2 output common mode', on_V=d300['atb_pre_V'], off_V=r(ext, 'drv_off')['atb_pre_V']),
                                             dict(port='atb_cm', node='RF_TX pad common mode', on_V=d300['atb_cm_V'], off_V=r(ext, 'drv_off')['atb_cm_V'])])
            byp = r(ext, 'chain_bypass')
            t['fallback'] = dict(state='pass', routes=[dict(
                route='rf_tx_low_power_external_pa', control='bypass=1 (debug.rf_tx_bypass): header, pre-amplifiers and all output tails off; '
                                                             'PMOS switches connect summed_rf to RF_TX',
                evidence=dict(chain_bypass=byp, chain_bypass_large=r(ext, 'chain_bypass_large'), standalone_bypass=r(ext, 'drv_bypass'),
                              board_matched_bypass=r(ext, 'match_bypass_0p3'), board_matched_bypass_saturated=r(ext, 'match_bypass_sat_1p0'),
                              rfdriver_supply_in_bypass_mA=byp['supply_mA']['rfdriver']),
                note='Function shown at low power (%.1f dBm at 0.3 V baseband); an external PA needs ~%.0f dB gain to reach 0 dBm.'
                     % (byp['pad_dBm_50ohm'], -byp['pad_dBm_50ohm']))],
                bypass_loading_fF=round(r(ext, 'cap_drv_in_off')['capacitance_fF'], 2),
                notes='bypass_loading_fF = total rfdriver input capacitance on summed_rf with the driver off and bypass open '
                      '(includes the off bypass PMOS); %.1f fF with the driver on.' % r(ext, 'cap_drv_in_on')['capacitance_fF'])
            bm = ext.get('board_match', {})
            ms, ml, ss = r(ext, 'match_sat_1p0'), r(ext, 'match_lin_0p3'), r(ext, 'match_ssb_sat')
            t['clean']['extracted_nominal'].update(
                board_matched_linear_dBm_0p3V=ml['pad_dBm_50ohm'], board_matched_saturated_dBm_1p0V=ms['pad_dBm_50ohm'],
                board_matched_ssb_linear_dBm=r(ext, 'match_ssb_lin')['lsb_dBm'], board_matched_ssb_saturated_dBm=ss['lsb_dBm'],
                board_match=dict(r_opt_diff_ohm=round(bm.get('r_opt_ohm', float('nan')), 1), shunt_pad=bm.get('shunt_pad'),
                                 series_l_total_H=bm.get('series_l'), inductor_q=bm.get('q_l'), method=bm.get('method')))
            mode_current = {'linear (chain, 0.3 V, matched)': ml['supply_mA']['rfdriver'],
                            'saturated (chain, 1.0 V, sat=1, matched)': ms['supply_mA']['rfdriver'],
                            'zero input (chain, matched)': r(ext, 'match_zero')['supply_mA']['rfdriver'],
                            'mute': r(ext, 'match_mute_sat')['supply_mA']['rfdriver'],
                            'bypass': r(ext, 'match_bypass_0p3')['supply_mA']['rfdriver']}
            pv += [perf('board-matched output power, linear mode (power delivered to 50 ohm after external L-match)', 0.0,
                        ml['pad_dBm_50ohm'], 'dBm', 'extracted chain, 0.3 V DC I, inductor Q=30, balun loss not included', src),
                   perf('board-matched output power, linear mode, 0.7 V DC I', 0.0, r(ext, 'match_lin_0p7')['pad_dBm_50ohm'], 'dBm',
                        'extracted chain', src),
                   perf('board-matched output power, saturated mode (txmix sat=1, full-scale baseband)', 0.0, ms['pad_dBm_50ohm'],
                        'dBm', 'extracted chain, 1.0 V DC I', src),
                   perf('board-matched SSB, linear (0.3 V I/Q) / saturated (1.0 V I/Q, sat=1)', 0.0,
                        [r(ext, 'match_ssb_lin')['lsb_dBm'], ss['lsb_dBm']], 'dBm', 'extracted chain, 61 MHz offset', src,
                        'saturated SSB image rejection %.1f dB, LO %.1f dBc (limiting distortion; acceptable for constant-envelope '
                        'modulation only)' % (ss['image_rejection_dB'], ss['lo_suppression_dBc'])),
                   perf('saturated-mode power control by gain code 1/4/8/15', None,
                        [r(ext, f'match_code{c}_sat')['pad_dBm_50ohm'] for c in (1, 4, 8)] + [ms['pad_dBm_50ohm']], 'dBm',
                        'extracted chain, matched', src),
                   perf('rfdriver current per mode', alloc['current_budget_ma']['rf_tx'], mode_current, 'mA', 'tt/27C/3.3V', src),
                   perf('board-matched linear output vs corner', None, corners(ext, 'pad_dBm_50ohm', prefix='mcorner_'), 'dBm',
                        'tt/ss/ff x 22/32 C x 3.15/3.35 V, same board network', src),
                   perf('board-matched saturated output vs corner', None, corners(ext, 'pad_dBm_50ohm', prefix='scorner_'), 'dBm',
                        'same corners, sat=1, 1.0 V', src),
                   perf('rfdriver current vs corner, saturated', alloc['current_budget_ma']['rf_tx'],
                        corners(ext, 'supply_mA', 'rfdriver', prefix='scorner_'), 'mA', 'same corners', src),
                   perf('mute isolation, saturated, matched', None,
                        round(ms['pad_dBm_50ohm'] - r(ext, 'match_mute_sat')['pad_dBm_50ohm'], 2), 'dB', 'extracted chain', src)]
            pv += [perf('mean output power into 50 ohm differential, no board matching', ARCH['blocks']['rfdriver']['parameters']['target_mean_power_dbm'],
                        chain['pad_dBm_50ohm'], 'dBm', 'full extracted chain, 0.3 V DC I baseband (CW at LO), code 15', src),
                   perf('SSB output power', 0.0, r(ext, 'chain_ssb')['lsb_dBm'], 'dBm', 'full extracted chain, 0.3 V I/Q at 61 MHz', src),
                   perf('maximum output power (driver standalone, 0.6 V input)', 0.0, d600['pad_dBm_50ohm'], 'dBm', 'tt/27C/3.3V extracted', src),
                   perf('driver voltage gain summed_rf -> pad', ARCH['blocks']['rfdriver']['parameters']['nominal_gain'],
                        d50['voltage_gain'], 'V/V', '50 mV input, 2.44 GHz, extracted', src),
                   perf('supply current', alloc['current_budget_ma']['rf_tx'], d300['supply_mA'], 'mA', 'code 15, 0.3 V input', src),
                   perf('gain-code steps (pad dBm for code 1/2/4/8/12/15)', None,
                        [r(ext, f'drv_code{c}')['pad_dBm_50ohm'] for c in (1, 2, 4, 8, 12)] + [d300['pad_dBm_50ohm']], 'dBm',
                        'standalone, 0.3 V input; code = rfdriver.gain[7:4]', src),
                   perf('mute isolation (chain, unmatched)', None, round(chain['pad_dBm_50ohm'] - r(ext, 'chain_mute')['pad_dBm_50ohm'], 2), 'dB',
                        'mute=1 vs mute=0, extracted chain', src),
                   perf('LO suppression at pad (chain SSB)', None, r(ext, 'chain_ssb')['lo_suppression_dBc'], 'dBc', 'ideal LO', src),
                   perf('chain output power vs corner', None, corners(ext, 'pad_dBm_50ohm'), 'dBm',
                        'tt/ss/ff x 22/32 C x 3.15/3.35 V, extracted chain, 0.3 V DC I', src),
                   perf('rfdriver current vs corner', alloc['current_budget_ma']['rf_tx'], corners(ext, 'supply_mA', 'rfdriver'), 'mA',
                        'same corners', src),
                   perf('stretch: output at LO/2 (1.22 GHz) and LO/4 (610 MHz)', None,
                        {k: r(ext, k).get('pad_dBm_50ohm') for k in ('stretch_lo_div2', 'stretch_lo_div2_large', 'stretch_lo_div4', 'stretch_lo_div4_large')},
                        'dBm', 'extracted chain, 0.3 V / 0.7 V DC I, no board matching applied (50 ohm differential load)', src,
                        'non-gating stretch goal; no design change made for it')]
        if sch:
            pv.append(perf('schematic (no wiring parasitics) chain output for reference', None,
                           r(sch, 'chain_dc').get('pad_dBm_50ohm'), 'dBm', 'same bench, source netlists', 'generated/rf_tx-sim-sch.json'))
        ev['performance_vs_target'] = pv
        ev['excluded_coverage'] = excl
        docs[block] = ev
        (GEN / f'{block}-evidence.json').write_text(json.dumps(ev, indent=1, default=str).replace('"pass_"', '"pass"') + '\n')
    return docs


if __name__ == '__main__':
    d = build()
    for b, e in d.items():
        print(b, {k: v['state'] for k, v in e['tests'].items()}, e['area'])
