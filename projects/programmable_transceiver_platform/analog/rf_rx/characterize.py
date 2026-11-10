"""Run every testbench of the RF receive family and write generated/<block>-evidence.json.

Usage:  python3 characterize.py [--quick] [--jobs N]
  --quick  nominal points only (skip the 12-corner sweeps and the chain transients)

Gating ('clean'): Magic DRC = 0, Netgen unique match, extracted nominal basic function
(tt, 27 C, 3.3 V).  Corners tt/ss/ff x 22/32 C x 3.15/3.35 V are recorded under
performance_vs_target and do not gate.
"""
import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rfrx_flow as flow
import simlib as S
import tb

HERE = flow.HERE
GEN = flow.GENERATED
WORK = flow.SCRATCH / 'char'
NOM = ('typical', 27, 3.3)
CORNERS = S.CORNERS
POOL = None


def par(fns):
    """Run thunks in parallel; exceptions are returned as {'error': str}."""
    def wrap(fn):
        try:
            return fn()
        except Exception as e:      # recorded, never hidden
            return {'error': str(e)[-600:]}
    return list(POOL.map(wrap, fns))


def layout(block):
    return json.loads((GEN / f'{block}-layout.json').read_text())


def clean_state(lay, nominal_ok):
    ok = lay['drc_count'] == 0 and lay['lvs']['unique_match'] and nominal_ok
    return 'pass' if ok else 'fail'


def base_record(block, lay):
    return {
        'block': block,
        'top_cell': f'pt_{block}',
        'source_hashes': {k: v for k, v in lay['sources'].items()},
        'artifact_hashes': lay['artifacts'],
        'images': {'analog': flow.ANALOG_IMAGE, 'analog_ref': flow.ANALOG_REF,
                   'digital': flow.DIGITAL_IMAGE, 'digital_tag': flow.DIGITAL_TAG},
        'pdk': 'gf180mcuD; ' + flow.PDK_NOTE,
        'area': {'bbox_um': lay['bbox_um'], 'area_um2': lay['area_um2']},
    }


def drc_lvs(lay):
    return ({'tool': 'Magic 8.3.623 drc(full), euclidean', 'errors': lay['drc_count'],
             'error_tiles': lay['drc_raw'], 'report': f"generated/{lay['block']}-layout.json",
             'klayout_crosscheck': lay.get('klayout_drc')},
            {'tool': 'Netgen 1.5.316 gf180mcuD_setup.tcl', 'result': lay['lvs']['final_result'],
             'unique_match': lay['lvs']['unique_match'], 'report': f"generated/{lay['block']}-lvs.txt"})


def corner_table(fn, keys):
    rows = par([lambda c=c: dict(corner={'mos': c[0], 'temp_c': c[1], 'vdd_v': c[2]}, **fn(c)) for c in CORNERS])
    return [{k: r.get(k) for k in ['corner', 'error'] + keys if k in r} for r in rows]


# ---------------------------------------------------------------- LNA (+ chain)
def do_lna(quick, chain):
    w = WORK / 'lna'
    lay = layout('lna')
    act, glo, byp, off, unp27, unp85, unp0, idle_hi = par([
        lambda: tb.lna_ac(w, 'ext', NOM, 'active'), lambda: tb.lna_ac(w, 'ext', NOM, 'gain_lo'),
        lambda: tb.lna_ac(w, 'ext', NOM, 'bypass'), lambda: tb.lna_ac(w, 'ext', NOM, 'off'),
        lambda: tb.lna_unpowered(w, 'ext', 27), lambda: tb.lna_unpowered(w, 'ext', 85),
        lambda: tb.lna_unpowered(w, 'ext', 0), lambda: tb.lna_ac(w, 'ext', ('typical', 85, 3.63), 'off')])
    sch = tb.lna_ac(w, 'sch', NOM, 'active')
    bm = tb.board_match(complex(act['zin_re_ohm'], act['zin_im_ohm']))
    actm = tb.lna_ac(w, 'ext', NOM, 'active', match=bm)
    byp_coff = tb.off_capacitance(w, 'lna_bypass', '\n'.join(
        f'XM{i} a off b VSS nfet_03v3 w=5u l=0.28u' for i in range(12)).replace('XM', 'MXM').replace('VSS', '0'), 2.4e9)
    nominal_ok = act.get('gain_db') is not None and act['idd_a'] > 1e-3
    rec = base_record('lna', lay)
    d, l = drc_lvs(lay)
    perf = [
        {'metric': 'voltage gain into 50 ohm/leg mixer-input model, 2.4 GHz (dB)', 'target': '20 (gain code 3)',
         'extracted_nominal': act.get('gain_db'), 'schematic_nominal': sch.get('gain_db')},
        {'metric': 'NF, 100 ohm diff source, no board match (dB)', 'target': 6.0, 'extracted_nominal': act.get('nf_db')},
        {'metric': 'NF with ideal lossless board L-match (dB)', 'target': 6.0, 'extracted_nominal': actm.get('nf_db'),
         'detail': {'match': bm, 'gain_db': actm.get('gain_db')}},
        {'metric': 'differential input impedance at 2.4 GHz (ohm)', 'target': '100 (board matching allowed)',
         'extracted_nominal': [act.get('zin_re_ohm'), act.get('zin_im_ohm')]},
        {'metric': 'gain_lo step (dB)', 'target': 'codes -6/0/10/20 dB', 'extracted_nominal':
            (glo['gain_db'] - act['gain_db']) if glo.get('gain_db') and act.get('gain_db') else None},
        {'metric': 'supply current active (mA)', 'target': 3.0, 'extracted_nominal': act['idd_a'] * 1e3 if act.get('idd_a') else None},
        {'metric': 'IIP3 (dBm)', 'target': 0.0, 'extracted_nominal': None, 'note': 'not simulated'},
    ]
    if chain:
        tl, tbp = chain.get('tnoise_lna_matched', {}), chain.get('tnoise_bypass', {})
        perf += [{'metric': 'chain NF incl. noise folding (transient noise, I output), board match: 5-9 MHz / 2-9 MHz band (dB)',
                  'target': 6.0, 'extracted_nominal': [tl.get('nf_i_5to9mhz_db'), tl.get('nf_i_db')], 'detail': tl},
                 {'metric': 'same with a board LNA (15 dB gain, 1.5 dB NF) ahead of the on-chip LNA (dB, Friis), 5-9 / 2-9 MHz',
                  'extracted_nominal': [tl.get('board_lna_15db_1p5db_nf_5to9mhz_db'), tl.get('board_lna_15db_1p5db_nf_db')]},
                 {'metric': 'chain NF via the LNA bypass (unmatched), 5-9 / 2-9 MHz, and with the board LNA 5-9 / 2-9 MHz (dB)',
                  'extracted_nominal': [tbp.get('nf_i_5to9mhz_db'), tbp.get('nf_i_db'), tbp.get('board_lna_15db_1p5db_nf_5to9mhz_db'),
                                        tbp.get('board_lna_15db_1p5db_nf_db')], 'detail': tbp},
                 {'metric': 'RF pad -> I/Q baseband conversion gain with LNA, no board match (dB)',
                  'extracted_nominal': chain.get('ext_u')},
                 {'metric': 'same with ideal lossless board L-match (dB)', 'extracted_nominal': chain.get('ext_m')}]
    if not quick:
        perf.append({'metric': 'corner sweep (ext, active)', 'rows': corner_table(
            lambda c: tb.lna_ac(w, 'ext', c, 'active'), ['gain_db', 'nf_db', 'idd_a', 'zin_re_ohm', 'zin_im_ohm'])})
    rec['tests'] = {
        'safe': {'state': 'pass' if (off.get('idd_a', 1) < 2e-5 and unp27.get('pad_current_a', 1) < 1e-6
                                     and unp85.get('pad_current_a', 1) < 1e-6 and unp0.get('pad_current_a', 1) < 1e-6
                                     and idle_hi.get('idd_a', 1) < 2e-5) else 'fail',
                 'cases': [
                     {'case': 'reset/off: all controls 0, island on 3.3 V', 'rail_current_a': off.get('idd_a'),
                      'note': 'includes the 10 uA reference only if it flowed from the rail; reference is a separate source here'},
                     {'case': 'off, 85 C, 3.63 V', 'rail_current_a': idle_hi.get('idd_a')},
                     {'case': 'island unpowered, controls and RF_RX_P at 3.63 V, 27 C', **unp27},
                     {'case': 'same, 85 C', **unp85}, {'case': 'same, 0 C', **unp0},
                     {'case': 'RF pad isolation with LNA off (gain to mixer node, dB)', 'value': off.get('gain_db')}],
                 'notes': 'Pad side of Cin is a MIM bottom plate (no junction on RF_RX). Tail/diode off and load '
                          'supply PMOS off at reset; island_off weakly clamps rf_out_p/n (W/L=1/10).'},
        'clean': {'state': clean_state(lay, nominal_ok), 'drc': d, 'lvs': l,
                  'extracted_nominal': {'condition': 'tt 27 C 3.3 V, extracted with parasitic C', **act}},
        'observable': {'state': 'pass' if act.get('vd_cm_v') else 'open',
                       'atb_taps': [{'port': 'atb_nbias', 'node': 'tail mirror gate (ibias diode)'},
                                    {'port': 'atb_vdcm', 'node': 'drain common mode via 2 x 20 kohm',
                                     'nominal_v': act.get('vd_cm_v')}],
                       'status_bits': [], 'clock_obs': [],
                       'notes': 'Register map ATB code 16 lna_bias; drain CM tap needs an ATB code at integration.'},
        'fallback': {'state': 'pass' if byp.get('gain_db') is not None else 'fail',
                     'routes': [{'route': 'rf_lna_bypass', 'control': 'byp=1 (debug.rf_rx_bypass.lna), en=0',
                                 'pads': ['RF_RX_P', 'RF_RX_N'],
                                 'bypass_gain_into_mixer_model_db': byp.get('gain_db'),
                                 'chain_conversion_gain_db': (chain or {}).get('ext_byp')}],
                     'bypass_loading_fF': byp_coff * 1e15 if byp_coff else None,
                     'bypass_loading_note': 'off-state capacitance of one 60/0.28 bypass NMOS seen from one side at 2.4 GHz (schematic device)'},
    }
    rec['performance_vs_target'] = perf
    rec['excluded_coverage'] = ['IIP3/P1dB not simulated', 'S11 with a real board network not simulated (ideal L-match only)',
                                'gain codes implemented: active (high) and gain_lo shunt only; -6/0/10/20 dB mapping open',
                                'ESD/pad network modelled as 0.5 pF per leg only', 'no Monte Carlo']
    return rec


# ---------------------------------------------------------------- mixers
def do_rxmix(block, quick, chain):
    w = WORK / block
    lay = layout(block)
    nom, sch, off, unp27, unp85, unp0, tri = par([
        lambda: tb.rxmix_tran(w, 'ext', NOM, block), lambda: tb.rxmix_tran(w, 'sch', NOM, block),
        lambda: tb.rxmix_dc(w, 'ext', block, 3.3, 0), lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 27, 3.63),
        lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 85, 3.63), lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 0, 3.63),
        lambda: tb.rxmix_dc(w, 'ext', block, 3.3, 0, 27, 0.0, vbb=1.65)])
    on_dc = tb.rxmix_dc(w, 'ext', block, 3.3, 1)
    cal = [] if quick else corner_table(lambda c: tb.rxmix_calibrate(w, 'ext', c, block), ['raw_offset_v', 'lsb_v', 'code', 'residual_v'])
    cal_nom = tb.rxmix_calibrate(w, 'ext', NOM, block)
    g = nom.get('conversion_gain_db')
    rec = base_record(block, lay)
    d, l = drc_lvs(lay)
    perf = [{'metric': 'conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB)', 'target': '0 (arch, voltage)',
             'extracted_nominal': g, 'schematic_nominal': sch.get('conversion_gain_db')},
            {'metric': 'supply current (mA)', 'target': 1.0, 'extracted_nominal': nom['idd_a'] * 1e3 if nom.get('idd_a') else None},
            {'metric': 'baseband output CM (V)', 'target': 1.65, 'extracted_nominal': nom.get('vcm_v')},
            {'metric': 'TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V)',
             'target': '|residual| < 10 mV referred to the filter input', 'extracted_nominal':
                 [cal_nom.get('raw_offset_v'), cal_nom.get('residual_v'), cal_nom.get('lsb_v')], 'detail': cal_nom}]
    if cal:
        perf.append({'metric': 'offset calibration across the envelope (ext; calibrated at each point)', 'rows': cal})
    if chain:
        perf.append({'metric': 'chain with LNA (see lna evidence)', 'extracted_nominal': chain.get('ext_u')})
    if not quick:
        perf.append({'metric': 'corner sweep (ext transient)', 'rows': corner_table(
            lambda c: tb.rxmix_tran(w, 'ext', c, block), ['conversion_gain_db', 'idd_a', 'bb_offset_v'])})
    rec['tests'] = {
        'safe': {'state': 'pass' if (off.get('rail_current_a', 1) < 2e-5 and unp27.get('rail_current_a', 1) < 1e-6
                                     and unp85.get('rail_current_a', 1) < 1e-6 and unp27.get('control_current_a', 1) < 1e-6
                                     and unp85.get('control_current_a', 1) < 1e-6) else 'fail',
                 'cases': [{'case': 'reset/off, island on', **off},
                           {'case': 'island unpowered, en/island_off/LO (pll island) at 3.63 V, 27 C; rf nodes have no DC source (behind LNA MIM caps)', **unp27},
                           {'case': 'same 85 C', **unp85}, {'case': 'same 0 C', **unp0}],
                 'notes': 'LO drives only NMOS gates (no junction to the pll island). OTA outputs high-Z when off.'},
        'clean': {'state': clean_state(lay, g is not None and g > 0), 'drc': d, 'lvs': l,
                  'extracted_nominal': {'condition': 'tt 27 C 3.3 V, extracted with parasitic C', **nom}},
        'observable': {'state': 'pass' if on_dc.get('rail_current_a') else 'open',
                       'offset_dac': {'pins': 'ofs0..ofs4 (magnitude), ofs_sign', 'calibration_nominal': cal_nom},
                       'atb_taps': [{'port': 'atb_vcm', 'node': 'TIA reference / output CM'},
                                    {'port': 'atb_vbp', 'node': 'OTA PMOS bias'}],
                       'status_bits': [], 'clock_obs': [],
                       'notes': 'Baseband output also observable through bb_tap (bbfilter obs_sel=1).'},
        'fallback': {'state': 'pass' if tri.get('forced_bb_current_a', 1) < 1e-6 else 'fail',
                     'routes': [{'route': 'rf_rx_external_downconverter',
                                 'control': 'rxmix en=0 and LO stopped (outputs tri-stated); bb_tap inj_en=1 + bbfilter inj=1',
                                 'pads': ['BB_I_P', 'BB_I_N', 'BB_Q_P', 'BB_Q_N'],
                                 'mixer_output_current_when_forced_a': tri.get('forced_bb_current_a')}],
                     'bypass_loading_fF': None,
                     'notes': 'The inject switch lives in bb_tap; the mixer only has to release rx_bb (verified).'},
    }
    rec['performance_vs_target'] = perf
    rec['excluded_coverage'] = ['LO assumed ideal 0/VDD 50% square (quadrature block output not co-simulated)',
                                'I/Q mismatch, IIP2/IIP3, noise figure, LO leakage not simulated', 'no Monte Carlo']
    return rec


# ---------------------------------------------------------------- baseband filter
BW7 = ('en', 'bw0', 'bw1', 'bw2', 'bw3')   # narrowest (all 4 bandwidth bits)
def pga_on(db):
    """Control set for PGA code `db` (-6..42 dB, netlists.GAIN_TABLE)."""
    import netlists
    k, c0, c1 = netlists.GAIN_TABLE[db]
    return ('en', *[f'gain{j}' for j in range(6) if k >> j & 1], *(('gainc0',) if c0 else ()), *(('gainc1',) if c1 else ()))


G15 = pga_on(42)     # top PGA code (name kept from the 4-bit version)
PGA_CODES = list(range(-6, 43, 3))


def do_bbf(block, quick):
    w = WORK / block
    lay = layout(block)
    A = lambda tag, **k: (lambda: tb.bbf_ac(w, 'ext', NOM, block, tag=tag, **k))
    names = ['rx', 'rx_bw7', 'rx_g15', 'tx', 'byp_s1', 'byp_s23', 'byp_both', 'rx_direct', 'rxd_txfilt',
             'obs1', 'obs2', 'obs3', 'inject', 'off_iso']
    runs = par([A('rx'), A('rx_bw7', on=BW7), A('rx_g15', on=G15),
                A('tx', on=('en', 'dir_tx'), src='tx', out='out_tx'),
                A('byp_s1', on=('en', 'byp_s1')), A('byp_s23', on=('en', 'byp_s23')),
                A('byp_both', on=('en', 'byp_s1', 'byp_s23')),
                A('rx_direct', on=('en', 'rx_direct')),
                A('rxd_txfilt', on=('en', 'rx_direct', 'dir_tx'), src='rx', out='out_rx'),
                A('obs1', on=('en', 'obs_sel0'), out='obs'), A('obs2', on=('en', 'obs_sel1'), out='obs'),
                A('obs3', on=('en', 'obs_sel0', 'obs_sel1'), out='obs'),
                A('inject', on=('en', 'inj'), inj_drive=True),
                A('off_iso', on=())])
    R = dict(zip(names, runs))
    pga = dict(zip(PGA_CODES, par([(lambda c=c: tb.bbf_ac(w, 'ext', NOM, block, on=pga_on(c), tag=f'pga{c}')) for c in PGA_CODES])))
    sch = tb.bbf_ac(w, 'sch', NOM, block, tag='rx')
    settle, off, unp27, unp85, unp0, unp_hi = par([
        lambda: tb.bbf_direction_settle(w, 'ext', NOM, block),
        lambda: tb.bbf_dc(w, 'ext', block, 3.3, ()),
        lambda: tb.bbf_dc(w, 'ext', block, 0, (), 27, 1.65), lambda: tb.bbf_dc(w, 'ext', block, 0, (), 85, 1.65),
        lambda: tb.bbf_dc(w, 'ext', block, 0, (), 0, 1.65), lambda: tb.bbf_dc(w, 'ext', block, 0, (), 27, 3.63)])
    cm16 = tb.bbf_cm_sensitivity(w, 'ext', NOM, block, on=G15)
    cm1 = tb.bbf_cm_sensitivity(w, 'ext', NOM, block)
    txo = par([lambda a=a: tb.tx_observe(w, 'ext', NOM, block, amp=a) for a in (0.2, 0.4, 0.8)])
    inc = f"{tb.netlist(w, block, 'sch')}"
    c_tgm = tb.off_capacitance(w, 'tgm', 'X1 a b off onb VDD 0 pt_rfrx_tgm', 10e6, include=inc)
    c_nsw = tb.off_capacitance(w, 'nsw', 'X1 a b off 0 pt_rfrx_nsw', 10e6, include=inc)
    rx = R['rx']
    nominal_ok = rx.get('f3db_hz') is not None and abs(rx.get('dc_gain_db', 99)) < 1.5
    rec = base_record(block, lay)
    d, l = drc_lvs(lay)
    perf = [
        {'metric': 'RX -3 dB cutoff, widest (bw=0) (Hz)', 'target': '>= 10e6 at tt and in the envelope (lead, Wi-Fi 20 MHz)',
         'extracted_nominal': rx.get('f3db_hz'), 'schematic_nominal': sch.get('f3db_hz')},
        {'metric': 'RX -3 dB cutoff, narrowest (bw=15) (Hz)', 'target': '1e5 min', 'extracted_nominal': R['rx_bw7'].get('f3db_hz')},
        {'metric': 'passband peaking at bw=0 (dB above DC)', 'target': '<= 1 dB ripple',
         'extracted_nominal': (rx['peak_gain_db'] - rx['dc_gain_db']) if rx.get('peak_gain_db') is not None else None},
        {'metric': 'PGA gain range (dB, code -6 .. 42)', 'target': '-6 .. 42 in 3 dB steps',
         'extracted_nominal': [pga[-6].get('dc_gain_db'), pga[42].get('dc_gain_db')]},
        {'metric': 'PGA code sweep, bw=0 (code dB: dc gain dB, peaking dB, f3db Hz)', 'target': '3 dB steps, <= 1 dB ripple, >= 10 MHz',
         'extracted_nominal': {c: [pga[c].get('dc_gain_db'), (pga[c]['peak_gain_db'] - pga[c]['dc_gain_db']) if pga[c].get('peak_gain_db') is not None else None,
                                   pga[c].get('f3db_hz')] for c in PGA_CODES}},
        {'metric': 'TX direction (tx_in -> out_tx) cutoff and gain', 'extracted_nominal': R['tx']},
        {'metric': 'stretch: gain at 20 MHz with widest setting (dB) (40 MHz channels need ~20 MHz corner)',
         'extracted_nominal': rx.get('gain_20mhz_db'), 'note': 'widest corner is far below 20 MHz'},
        {'metric': 'supply current, RX active (mA)', 'target': 4.5, 'extracted_nominal': rx['idd_a'] * 1e3 if rx.get('idd_a') else None},
        {'metric': 'output CM minus input CM with input CM at 1.75 V (V), gain 1 / gain 16 (OTAs reference the input CM)',
         'target': 'no PGA-gain multiplication', 'extracted_nominal': [cm1.get('out_cm_minus_in_cm_v'), cm16.get('out_cm_minus_in_cm_v')]},
        {'metric': 'passband peaking at max PGA gain (dB above DC)', 'target': '<= 1 dB ripple',
         'extracted_nominal': (R['rx_g15']['peak_gain_db'] - R['rx_g15']['dc_gain_db']) if R['rx_g15'].get('peak_gain_db') is not None else None},
        {'metric': 'TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc)',
         'extracted_nominal': [txo[0].get('f3db_hz'), txo[0].get('lf_gain_db'), txo[1].get('hd3_dbc'), txo[2].get('hd3_dbc')]},
        {'metric': 'TX->RX direction switch settling to 1 % (s)', 'target': 1e-6, 'extracted_nominal': settle.get('settle_1pct_after_switch_s'),
         'detail': settle},
    ]
    if not quick:
        perf.append({'metric': 'corner sweep (ext, RX widest, gain 0)', 'rows': corner_table(
            lambda c: tb.bbf_ac(w, 'ext', c, block, tag='rx'), ['f3db_hz', 'dc_gain_db', 'peak_gain_db', 'idd_a', 'out_cm_v'])})
        perf.append({'metric': 'corner sweep (ext, RX top PGA code 42 dB)', 'rows': corner_table(
            lambda c: tb.bbf_ac(w, 'ext', c, block, on=G15, tag='rx_g15'), ['dc_gain_db', 'peak_gain_db', 'f3db_hz', 'out_cm_v'])})
        perf.append({'metric': 'corner sweep (ext, RX PGA code 21 dB: first coarse step)', 'rows': corner_table(
            lambda c: tb.bbf_ac(w, 'ext', c, block, on=pga_on(21), tag='rx_g21'), ['dc_gain_db', 'peak_gain_db', 'f3db_hz'])})
    ok_byp = all(R[k].get('dc_gain_db') is not None and abs(R[k]['dc_gain_db']) < 3
                 for k in ('byp_s1', 'byp_s23', 'byp_both', 'rx_direct', 'inject', 'rxd_txfilt'))
    ok_obs = all(R[k].get('dc_gain_db') is not None and abs(R[k]['dc_gain_db']) < 3 for k in ('obs1', 'obs2', 'obs3'))
    rec['tests'] = {
        'safe': {'state': 'pass' if (off.get('rail_current_a', 1) < 1e-6 and unp27.get('tx_in_current_a', 1) < 1e-6
                                     and unp85.get('tx_in_current_a', 1) < 1e-6
                                     and unp_hi.get('tx_in_current_a', 1) < 1e-6) else 'fail',
                 'cases': [{'case': 'reset/off: all controls 0, island on', **off},
                           {'case': 'island off (VDD=0, island_off=1); DAC (tx_in) and ADC (out_rx) nodes driven to 1.65 V, 27 C', **unp27},
                           {'case': 'same 85 C', **unp85}, {'case': 'same 0 C', **unp0},
                           {'case': 'same with peer nodes at 3.63 V', **unp_hi},
                           {'case': 'filter off: rx_in -> out_rx isolation (dB)', 'value': R['off_iso'].get('dc_gain_db')}],
                 'notes': 'Cross-island pins (tx_in from DAC, out_rx to ADC) use NMOS-only switches: no PMOS junction to '
                          'VDD_RF_SW. out_rx current with the island off is the weak island_off clamp (W/L=1/10).'},
        'clean': {'state': clean_state(lay, nominal_ok), 'drc': d, 'lvs': l,
                  'extracted_nominal': {'condition': 'tt 27 C 3.3 V, extracted with parasitic C, RX direction, bw=0, gain=0', **rx}},
        'observable': {'state': 'pass' if ok_obs else 'fail',
                       'atb_taps': [{'port': 'atb_vcm', 'nominal_v': rx.get('vcm_v')}, {'port': 'atb_vbp'}],
                       'observe_mux': {'obs_sel=1 rx_in (after mixer)': R['obs1'], 'obs_sel=2 after PGA stage': R['obs2'],
                                       'obs_sel=3 filter output': R['obs3']},
                       'status_bits': [], 'clock_obs': []},
        'fallback': {'state': 'pass' if ok_byp else 'fail',
                     'routes': [
                         {'route': 'rf_bb_stage_bypass', 'control': 'byp_s1 (debug.rf_bb_bypass.pga), byp_s23 (debug.rf_bb_bypass.rxfilter)',
                          'byp_s1': R['byp_s1'], 'byp_s23': R['byp_s23'], 'both': R['byp_both']},
                         {'route': 'rf_bb_external_adc', 'control': 'obs_sel 1/2/3 -> bb_tap', 'see': 'observable.observe_mux'},
                         {'route': 'rf_rx_external_downconverter', 'control': 'inj=1 (+ bb_tap inj_en)', 'inject_to_out_rx': R['inject']},
                         {'route': 'loopback: TX through filter while RX goes filter-less', 'control': 'dir_tx=1, rx_direct=1',
                          'rx_in_to_out_rx': R['rxd_txfilt']},
                         {'route': 'rx_direct (filter-less RX)', 'rx_in_to_out_rx': R['rx_direct']},
                         {'route': 'rf_tx_external_upconverter (for txmix/txsum)',
                          'control': 'direction=tx, obs_sel=11 (bb_tap observe_tx), bb_tap obs_en=1',
                          'dac_in_to_bb_pad_10pF': txo}],
                     'bypass_loading_fF': {'tgm_off_10MHz': c_tgm * 1e15 if c_tgm else None,
                                           'nsw_off_10MHz': c_nsw * 1e15 if c_nsw else None},
                     'bypass_loading_note': 'schematic-device off capacitance of one bypass TG (n 10 / p 20) and one NMOS-only switch (30/0.28)'},
    }
    rec['performance_vs_target'] = perf
    rec['excluded_coverage'] = ['Q tuning codes (q1/q2) and zero-position codes not implemented: fixed pre-distorted Butterworth Qs',
                                'cutoff programmable over 4 bits (x1..x16 capacitance) only; arch cutoff_code is 8 bits',
                                'PGA -6..42 dB: stage-1 conductance k/4 (6 bits) x two +12 dB biquad steps (gainc0/1); code table netlists.GAIN_TABLE (register -> bits LUT in the digital); offset correction lives in the mixer TIA (rxmix ofs DAC), not in the filter',
                                'narrowest corner limited by the 1..16x capacitor bank (LoRa 203/406 kHz needs ~4x more range): open',
                                'finite-zero (elliptic) option removed: the extracted single-zero version gave no useful notch; all-pole only',
                                'noise not simulated; linearity only via the TX-observe HD3 points',
                                'no Monte Carlo']
    return rec


# ---------------------------------------------------------------- bb_tap
def do_tap(quick):
    w = WORK / 'bb_tap'
    lay = layout('bb_tap')
    obs, inj, off33, off0, off85, off0c, offlo = par([
        lambda: tb.tap_observe(w, 'ext', NOM), lambda: tb.tap_inject(w, 'ext', NOM),
        lambda: tb.tap_off(w, 'ext', 3.3, 27, 3.63), lambda: tb.tap_off(w, 'ext', 0, 27, 3.63),
        lambda: tb.tap_off(w, 'ext', 0, 85, 3.63), lambda: tb.tap_off(w, 'ext', 0, 0, 3.63),
        lambda: tb.tap_off(w, 'ext', 3.3, 27, 0.0)])
    sch = tb.tap_observe(w, 'sch', NOM)
    pad_c = tb.off_capacitance(w, 'tap_pad', '\n'.join(
        [f'MXS{i} b off a 0 nfet_03v3 w=5u l=0.28u' for i in range(12)] +
        [f'MXJ{i} a off b 0 nfet_03v3 w=5u l=0.28u' for i in range(8)]), 20e6)
    nominal_ok = obs.get('lf_gain_db') is not None and obs['lf_gain_db'] > -6 and inj.get('pad_to_node_gain_db', -99) > -1
    rec = base_record('bb_tap', lay)
    d, l = drc_lvs(lay)
    perf = [{'metric': 'observe gain in -> pad, 10 pF || 100 k load (dB)', 'target': '~0 (buffer)', 'extracted_nominal': obs.get('lf_gain_db'),
             'schematic_nominal': sch.get('lf_gain_db')},
            {'metric': 'observe -3 dB bandwidth into 10 pF (Hz)', 'target': '>= 20e6', 'extracted_nominal': obs.get('f3db_hz')},
            {'metric': 'gain at 20 MHz (dB), AC / transient 0.4 Vpp diff', 'extracted_nominal': [obs.get('gain_20mhz_db'), obs.get('tran_gain_20mhz_db')]},
            {'metric': 'pad common mode in observe (V)', 'extracted_nominal': obs.get('pad_cm_v'),
             'note': 'NMOS follower level shift; external ADC must accept ~0.8 V CM'},
            {'metric': 'inject pad -> chain node gain (dB)', 'extracted_nominal': inj.get('pad_to_node_gain_db')},
            {'metric': 'supply current observing (mA)', 'extracted_nominal': obs['idd_a'] * 1e3 if obs.get('idd_a') else None}]
    if not quick:
        perf.append({'metric': 'corner sweep (ext observe)', 'rows': corner_table(
            lambda c: tb.tap_observe(w, 'ext', c), ['lf_gain_db', 'f3db_hz', 'gain_20mhz_db', 'pad_cm_v', 'idd_a'])})
    rec['tests'] = {
        'safe': {'state': 'pass' if all(x.get('pad_current_a', 1) < 1e-6 for x in (off33, off0, off85, off0c, offlo))
                 and off33.get('rail_current_a', 1) < 1e-6 else 'fail',
                 'cases': [{'case': 'tap off, island on, pad_p forced 3.63 V', **off33},
                           {'case': 'island off, inj_en=3.63 V (core domain), pad_p 3.63 V, 27 C', **off0},
                           {'case': 'same 85 C', **off85}, {'case': 'same 0 C', **off0c},
                           {'case': 'tap off, island on, pad_p forced 0 V', **offlo}],
                 'notes': 'Only NMOS drains touch the pads (no PMOS junction to the island rail); inject gate is '
                          're-driven from the island rail so it is 0 V whenever the island is off.'},
        'clean': {'state': clean_state(lay, nominal_ok), 'drc': d, 'lvs': l,
                  'extracted_nominal': {'condition': 'tt 27 C 3.3 V, extracted with parasitic C', 'observe': obs, 'inject': inj}},
        'observable': {'state': 'pass', 'atb_taps': [{'port': 'atb_nbias', 'node': 'follower sink mirror gate'}],
                       'status_bits': [], 'clock_obs': [], 'notes': 'The block is itself the analog observation path.'},
        'fallback': {'state': 'pass' if nominal_ok else 'fail',
                     'routes': [{'route': 'rf_bb_external_adc', 'control': 'obs_en=1', 'pads': ['BB_I_P/N', 'BB_Q_P/N']},
                                {'route': 'rf_rx_external_downconverter / rf_tx_external_baseband', 'control': 'inj_en=1'}],
                     'bypass_loading_fF': pad_c * 1e15 if pad_c else None,
                     'bypass_loading_note': 'disabled capacitance added to one BB pad by both off NMOS switches (schematic devices, 20 MHz)'},
    }
    rec['performance_vs_target'] = perf
    rec['excluded_coverage'] = ['pad protection network not co-simulated (pad modelled as ideal node + 10 pF)',
                                'linearity/THD, noise not quantified', 'no Monte Carlo']
    return rec


def run_chain(quick, resume=False):
    w = WORK / 'chain'
    old = json.loads((GEN / 'rf_rx_chain.json').read_text()) if resume and (GEN / 'rf_rx_chain.json').exists() else {}
    act = tb.lna_ac(w, 'ext', NOM, 'active')
    m = tb.board_match(complex(act['zin_re_ohm'], act['zin_im_ohm']))
    jobs = {'ext_u': lambda: tb.chain_tran(w, 'ext'), 'ext_m': lambda: tb.chain_tran(w, 'ext', match=m),
            'ext_byp': lambda: tb.chain_tran(w, 'ext', mode='bypass')}
    if not quick:
        for f in (1.2e9, 0.6e9):
            def lo_job(f=f):
                a = tb.lna_ac(w, 'ext', NOM, 'active', f=f)
                mm = tb.board_match(complex(a['zin_re_ohm'], a['zin_im_ohm']), f=f)
                return tb.chain_tran(w, 'ext', flo=f, fif=2e6, match=mm)
            jobs[f'ext_m_{int(f / 1e6)}MHz'] = lo_job
    def tn_job(mode):
        def job():
            kc = tb.trnoise_calibration(w)
            en = tb.ota_input_noise(w)
            lm = tb.lna_ac(w, 'ext', NOM, 'active', match=m)
            r = tb.chain_tnoise(w, 'ext', kc, lm['nf_db'], en, mode, m if mode == 'lna' else None)
            r['board_lna_15db_1p5db_nf_db'] = tb.friis(1.5, 15., r['nf_i_db'])
            r['board_lna_15db_1p5db_nf_5to9mhz_db'] = tb.friis(1.5, 15., r['nf_i_5to9mhz_db'])
            return r
        return job
    jobs['tnoise_lna_matched'] = tn_job('lna')
    jobs['tnoise_bypass'] = tn_job('bypass')
    keep = {k: v for k, v in old.items() if k in jobs and isinstance(v, dict) and 'error' not in v}
    todo = [k for k in jobs if k not in keep]
    res = dict(keep, **dict(zip(todo, par([jobs[k] for k in todo]))))
    res = {k: res[k] for k in jobs}
    (GEN / 'rf_rx_chain.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    return res


def main():
    global POOL
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--resume-chain', action='store_true', help='reuse error-free chain results from generated/rf_rx_chain.json')
    ap.add_argument('--blocks', nargs='*', default=['chain', 'lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'bb_tap'])
    a = ap.parse_args()
    POOL = ThreadPoolExecutor(a.jobs)
    chain = None
    if 'chain' in a.blocks:
        chain = run_chain(a.quick, a.resume_chain)
    elif (GEN / 'rf_rx_chain.json').exists():
        chain = json.loads((GEN / 'rf_rx_chain.json').read_text())
    for b in a.blocks:
        if b == 'chain':
            continue
        if b == 'lna':
            rec = do_lna(a.quick, chain)
        elif b.startswith('rxmix'):
            rec = do_rxmix(b, a.quick, chain)
        elif b.startswith('bbfilter'):
            rec = do_bbf(b, a.quick)
        else:
            rec = do_tap(a.quick)
        (GEN / f'{b}-evidence.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
        print(b, {k: v['state'] for k, v in rec['tests'].items()})


if __name__ == '__main__':
    main()
