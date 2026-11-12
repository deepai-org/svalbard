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
import netlists as N  # noqa: E402
GEN = flow.GENERATED
WORK = flow.SCRATCH / 'char'
NOM = ('typical', 27, 3.3)
# chain NF (LNA + mixer, DSB, tt, extracted + Rg + pad) without the baseband filter: generated/rf_rx_chain.json
# det_lna_matched_extpr.nf_dsb_db (fork P/R); the filter's own penalty is added in do_bbf (fork U)
CHAIN_NF_DSB_DB = None   # fork B: read at run time (bbf_bench.chain_ref, generated/rf_rx_chain.json)
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
    # package-tolerance network (RC-8a/RC-9/RC-10): C-trim codes, SE mode, opt-in 200 ohm termination;
    # each point re-matched (ideal lossless board L-match), as the per-board calibration would
    def trim_point(ct, se=False, rt=False):
        u = tb.lna_ac(w, 'ext', NOM, 'active', ct=ct, se=se, rt=rt)
        if u.get('zin_re_ohm') is None:
            return {'unmatched': u}
        mm = tb.board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']))
        return {'unmatched': u, 'matched': tb.lna_ac(w, 'ext', NOM, 'active', match=mm, ct=ct, se=se, rt=rt),
                'match_q': mm.get('q')}
    R = tb.LNA_CT_RESET
    TRIM = [(0, False, False), (15, False, False), (R, False, True), (R, True, False)]
    trims = dict(zip([f'ct{c}{"_se" if s else ""}{"_rt" if r else ""}' for c, s, r in TRIM],
                     par([(lambda a=a: trim_point(*a)) for a in TRIM])))
    # fork P: in-band match with a per-board ladder (lna_match.py), envelope + pessimistic views
    import lna_match as LM
    PROCS = ('typical', 'ss', 'ff')
    # RC-16h (user decision 2026-11-12): board trimmer network lna_match.BOARD_TRIM (lossy parts, pessimistic Q),
    # trimmers + ct + rt set once per board; verified on the 0.5 MHz grid incl. 2.400/2.4835 GHz and the +-5 MHz guard
    BT = LM.BOARD_TRIM
    def trim_view(view):
        cns = [NOM] if quick else CORNERS
        zz = {rt: dict(zip(cns, par([(lambda c=c, rt=rt: LM.zsweep(w / f'zs_{view}', view, c, rt=rt)) for c in cns])))
              for rt in (False, True)}
        procs = [p_ for p_ in PROCS if any(c[0] == p_ for c in cns)]
        chips = {p_: ((zz[False], zz[True]), [c for c in cns if c[0] == p_]) for p_ in procs}
        f, ch = LM.trim_chips(chips)
        net = [tuple(x) for x in BT['net']]
        table = {p_: [(d,) + LM.trim_best(ch[p_], f, net, LM.BOND, BT['ratio'], d, ngrid=13) for d in LM._draws()] for p_ in procs}
        jobs, nets = [], {}
        for p_ in procs:
            nom = [r for r in table[p_] if r[0] == (0., 0., 0.)][0]
            worst = max(table[p_], key=lambda r: r[1])
            for lab, (d, _, st) in (('nominal parts and bond', nom), ('worst tolerance draw', worst)):
                m = dict(order='ladder', lossy=True, lb=LM.BOND, lb_actual=LM.BOND + d[0], net=[list(x) for x in st['net']], ct=st['ct'], rt=st['rt'])
                if lab.startswith('nominal'):
                    nets[p_] = m
                jobs += [(lab, d, m, c) for c in chips[p_][1]]
        res = par([(lambda j=j: tb.lna_band(w / f'band_{view}', view, j[3], j[2], ct=j[2]['ct'], rt=bool(j[2]['rt']))) for j in jobs])
        rows = []
        for (lab, d, m, c), r in zip(jobs, res):
            row = dict(corner={'mos': c[0], 'temp_c': c[1], 'vdd_v': c[2]}, case=lab,
                       draw={'bond_dnh': round(d[0] * 1e9, 2), 'L_tol': d[1], 'C_tol': d[2]}, ct=m['ct'], rt=m['rt'],
                       trimmers_pf=[round(v * 1e12, 3) for t, v in m['net'] if t == 'pT'])
            if 'error' in r:
                rows.append(dict(row, error=r['error'])); continue
            gw = [x for x in r['rows'] if 2.3949e9 <= x['f'] <= 2.48851e9]
            bd = [x for x in r['rows'] if 2.3999e9 <= x['f'] <= 2.48351e9]
            rows.append(dict(row, idd_a=r['idd_a'], s11_worst_db=round(max(x['s11_db'] for x in gw), 2),
                             s11_worst_db_band_only=round(max(x['s11_db'] for x in bd), 2),
                             nf_db=[round(min(x['nf_db'] for x in bd), 2), round(max(x['nf_db'] for x in bd), 2)],
                             gain_db=[round(min(x['gain_db'] for x in bd), 2), round(max(x['gain_db'] for x in bd), 2)]))
        tol = {p_: [dict(draw={'bond_dnh': round(d[0] * 1e9, 2), 'L_tol': d[1], 'C_tol': d[2]}, s11_worst_db=round(sw, 2),
                         ct=st['ct'], rt=st['rt'], trimmers_pf=[round(x * 1e12, 3) for x in st['trim']]) for d, sw, st in table[p_]]
               for p_ in procs}
        return rows, nets, tol
    band_pr, nets_pr, tol_pr = trim_view('extpr')
    band_pp, nets_pp, tol_pp = trim_view('extpp')     # NF/gain-worst end: Rg 200, +25 % device C, pad C +30 %
    band_lo, nets_lo, tol_lo = trim_view('extlo')     # match-worst end: Rg 60, no extra C, pad C -20 %
    # stability (review lna2 item 4): bond + supply L, K/mu two-port, Re(Zin) with the real extracted mixers, states
    ST_CASES = [('extlo', ('ff', 22, 3.35)), ('extlo', NOM), ('extpp', ('ss', 32, 3.15))]
    ST_STATES = [dict(ct=0), dict(ct=15), dict(ct=7, rt=True), dict(ct=7, att=63), dict(ct=7, mode='bypass')]
    stab = par([(lambda v=v, c=c, st=st: dict(view=v, corner=c, state=st, **LM.stability(w / 'stab', v, c, **st)))
                for v, c in (ST_CASES[:1] if quick else ST_CASES) for st in ST_STATES])
    import bench_selftest
    selftest = bench_selftest.run(w / 'selftest')
    ATT_CASES = [('extpr', NOM)] if quick else [('extpr', NOM), ('extpp', ('ss', 32, 3.15)), ('extpp', ('ss', 22, 3.15)),
                                                  ('extlo', ('ff', 22, 3.35)), ('extlo', ('ff', 32, 3.35))]
    NETS = {'extpr': nets_pr, 'extpp': nets_pp, 'extlo': nets_lo}
    att_sw = par([(lambda v=v, c=c: LM.att_sweep(w / 'att', v, c, NETS[v][c[0]], NETS[v][c[0]]['ct'])) for v, c in ATT_CASES])
    # max input (RF-RX-MAXIN): BLE -10 dBm with the full attenuator, Wi-Fi/15.4 -20 dBm; LNA compression
    cmp_cases = [(-10., 63), (-10., 31), (-20., 63), (-20., 0)]
    cmp_rows = par([(lambda p_=p_, a_=a_: tb.lna_compression(w / 'cmp', 'extpr', NOM, nets_pr['typical'], p_,
                                                              att=a_ & 31, gain_lo=bool(a_ & 32), ct=nets_pr['typical']['ct'],
                                                              rt=bool(nets_pr['typical']['rt'])))
                    for p_, a_ in cmp_cases])
    byp_coff = tb.off_capacitance(w, 'lna_bypass', '\n'.join(
        f'XM{i} a off b VSS nfet_03v3 w=5u l=0.28u' for i in range(12)).replace('XM', 'MXM').replace('VSS', '0'), 2.4e9)
    nominal_ok = act.get('gain_db') is not None and act['idd_a'] > 1e-3
    rec = base_record('lna', lay)
    d, l = drc_lvs(lay)
    perf = [
        {'metric': 'voltage gain into 50 ohm/leg mixer-input model, 2.4 GHz, no board match (dB)', 'target': 'information',
         'extracted_nominal': act.get('gain_db'), 'schematic_nominal': sch.get('gain_db')},
        {'metric': 'NF, 100 ohm diff source, no board match (dB)', 'target': 6.0, 'extracted_nominal': act.get('nf_db')},
        {'metric': 'NF with ideal lossless board L-match (dB)', 'target': 6.0, 'extracted_nominal': actm.get('nf_db'),
         'detail': {'match': bm, 'gain_db': actm.get('gain_db')}},
        {'metric': 'differential input impedance at 2.4 GHz (ohm)', 'target': '100 (board matching allowed)',
         'extracted_nominal': [act.get('zin_re_ohm'), act.get('zin_im_ohm')]},
        {'metric': 'pre-LNA attenuator att[4:0] + gain_lo (6 bits, code bit 5 = gain_lo; weights 1/3/7/16/40/120 x 3.4 um): attenuation levels at 2.442 GHz (dB), nominal and both uncertainty ends',
         'target': '>= 30 dB range, level gaps <= 6 dB (RF-RX-AGC, RXR-01)',
         'extracted': [{'view': v, 'corner': c, 'range_db': a.get('range_db'), 'max_level_gap_db': a.get('max_level_gap_db'),
                        'levels_db': a.get('att_levels_db')} for (v, c), a in zip(ATT_CASES, att_sw)],
         'pass': all(a.get('range_db', 0) >= 30 and a.get('max_level_gap_db', 99) <= 6 for a in att_sw),
         'note': 'gate-shunt attenuation: the input match is not held while attenuating (S11 per code in the detail)',
         'detail': att_sw},
        {'metric': 'LNA gain compression at the maximum input (RF-RX-MAXIN), tt 27 C 3.3 V, board ladder; (p_dBm, code) -> compression dB',
         'target': '<= 1 dB at -10 dBm (BLE) with the attenuator; <= 1 dB at -20 dBm (Wi-Fi/15.4)',
         'extracted_nominal': cmp_rows,
         'pass': all((r.get('compression_db') is not None and r['compression_db'] <= 1.0) for r, (p_, a_) in zip(cmp_rows, cmp_cases) if a_ == 63)},
        {'metric': 'supply current active (mA)', 'target': '<= 11.7 (power budget LNA allocation)',
         'extracted_nominal': act['idd_a'] * 1e3 if act.get('idd_a') else None},
        {'metric': f'package-tolerance network at reset (ct={tb.LNA_CT_RESET}, se=0, rt=0) vs other codes: matched NF / gain (dB), Zin (ohm), match Q',
         'target': 'trim/SE/RT network costs <= 0.5 dB NF (item 2); rt is opt-in',
         'extracted_nominal': {f'ct{tb.LNA_CT_RESET} (reset)': [actm.get('nf_db'), actm.get('gain_db'), act.get('zin_re_ohm'), act.get('zin_im_ohm'), bm.get('q')],
                               **{k: [v.get('matched', {}).get('nf_db'), v.get('matched', {}).get('gain_db'),
                                      v['unmatched'].get('zin_re_ohm'), v['unmatched'].get('zin_im_ohm'), v.get('match_q')]
                                  for k, v in trims.items()}},
         'note': 'ct: 4-bit shunt-C trim (RC-16e). se: RF_RX_N to VSS through an 11.6 um MIM. '
                 'rt: Q-spoil, 2 x ~1.5 kohm across the stage-1 gates (RC-16h).'},
        {'metric': 'in-band match with the BOARD TRIMMER network (lna_match.BOARD_TRIM, B18/B25; lossy parts at pessimistic Q, '
                   'trimmer ESL/terminal C), trimmers + ct (4..10) + rt set once per board, held over the four T/V points; '
                   'ngspice lna_band on a 0.5 MHz grid: S11 worst over 2.395-2.4885 GHz (band + 5 MHz guard), NF/gain over 2.400-2.4835 GHz. '
                   'View extpr = extracted + pad_rf_pair + Rg 150 ohm/10 um. Cases: nominal parts/bond and the worst tolerance draw',
         'target': 'S11 <= -10 dB (band + guard) at every envelope corner and tolerance case; ct in 4..10; NF <= 6.0 dB',
         'board_trim': BT, 'networks': nets_pr, 'rows': band_pr, 'tolerance_table_numpy': tol_pr,
         'pass': all(r.get('s11_worst_db', 0) <= -10 and r['nf_db'][1] <= 6.0 and 4 <= r['ct'] <= 10 for r in band_pr)
                 and all(t['s11_worst_db'] <= -10 for v in tol_pr.values() for t in v)},
        {'metric': 'same at the HIGH end of the uncertain values (NF / gain worst): Rg 200 ohm/10 um, +25 % device C (low fT), '
                   'RF pad C +30 %; NF limit applied to the derated NF (simulated + 1.5 dB model derate, spec/design-assumptions.md)',
         'target': 'S11 <= -10 dB (band + guard); derated NF <= 6.0 dB at every envelope corner',
         'networks': nets_pp, 'rows': [dict(r, nf_db_derated=[round(x + 1.5, 2) for x in r['nf_db']]) if 'nf_db' in r else r for r in band_pp],
         'tolerance_table_numpy': tol_pp,
         's11_pass': all(r.get('s11_worst_db', 0) <= -10 for r in band_pp) and all(t['s11_worst_db'] <= -10 for v in tol_pp.values() for t in v),
         'nf_pass': all(r['nf_db'][1] + 1.5 <= 6.0 for r in band_pp if 'nf_db' in r),
         'pass': all(r.get('s11_worst_db', 0) <= -10 and r['nf_db'][1] + 1.5 <= 6.0 for r in band_pp)
                 and all(t['s11_worst_db'] <= -10 for v in tol_pp.values() for t in v)},
        {'metric': 'same at the LOW end of the uncertain values (match / detuning / stability worst): Rg 60 ohm/10 um, no extra device C, '
                   'RF pad C -20 %',
         'target': 'S11 <= -10 dB (band + guard) at every envelope corner and tolerance case; ct within 4..10',
         'networks': nets_lo, 'rows': band_lo, 'tolerance_table_numpy': tol_lo,
         'pass': all(r.get('s11_worst_db', 0) <= -10 and 4 <= r['ct'] <= 10 for r in band_lo)
                 and all(t['s11_worst_db'] <= -10 for v in tol_lo.values() for t in v)},
        {'metric': 'stability: LNA two-port with 1.5 nH RF bonds and 1 nH VDD/VSS bonds (no off-chip decap credited); Edwards-Sinsky mu '
                   'and Rollett K from Z-parameters, 0.1-12 GHz; and min Re(Zin) at the pads with the REAL extracted rxmix_i/q attached '
                   '(LO static, both polarities). States: ct 0 / 15, rt on, full attenuation (63), bypass',
         'target': 'mu > 1 at every frequency (unconditional), or, if not, Re(Zin) > 0 with the real source/load terminations',
         'extracted': stab,
         'unconditional': all((r.get('min_mu') or 0) > 1 for r in stab),
         'pass': all((r.get('min_re_zin_real_mixer_ohm') or -1) > 0 for r in stab)},
        {'metric': 'bench self-tests (bench_selftest.py): hand-calculable and deliberately broken cases of the LNA NF, S11-ladder and '
                   'harmonic-noise benches',
         'target': 'every ok case passes; every broken case fails its check', 'extracted': selftest, 'pass': bool(selftest.get('all_ok'))},
        {'metric': 'IIP3 (dBm)', 'target': 0.0, 'extracted_nominal': None, 'note': 'not simulated'},
    ]
    if chain:
        dn, ds = chain.get('det_lna_matched_extpr', {}), chain.get('det_lna_matched_extpr_ss_32_3.15', {})
        perf += [{'metric': 'chain NF, deterministic multitone (tb.chain_det), extpr view, per-board ladder: DSB (zero-IF) / SSB (I channel) (dB); '
                            'LNA noise at 3 fLO / 5 fLO measured (lna_harmonic), not assumed',
                  'target': 'on-chip <= 4.1 DSB (RF-RX-NFSYS 8 dB system - 3.91 dB board budget)',
                  'extracted_nominal': [dn.get('nf_dsb_db'), dn.get('nf_ssb_db')],
                  'extracted_ss_32c_3v15': [ds.get('nf_dsb_db'), ds.get('nf_ssb_db')],
                  'pass': all(x is not None and x <= 4.1 for x in (dn.get('nf_dsb_db'), ds.get('nf_dsb_db'))),
                  'pessimistic_note': 'the +1.5 dB model derate on the LNA is not applied here (see the RFR-01 row)',
                  'detail': {'tt': dn, 'ss_32_3.15': ds}},
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
    for r in perf:   # fork P: every row carries a pass field ('info' = no numeric target)
        if 'pass' not in r:
            if r['metric'].startswith('NF with ideal lossless board L-match'):
                r['pass'] = r.get('extracted_nominal') is not None and r['extracted_nominal'] <= 6.0
            elif r['metric'].startswith('supply current active'):
                r['pass'] = r.get('extracted_nominal') is not None and r['extracted_nominal'] <= 11.7
            else:
                r['pass'] = 'info'
    rec['performance_vs_target'] = perf
    rec['excluded_coverage'] = ['IIP3 not simulated (compression at the maximum input only)',
                                'board network: ideal lossless ladder parts (Q 20 part loss and balun loss are in the board budget, B18)',
                                'MIM bottom-plate parasitic beyond extraction (pessimistic 15 %) not added',
                                'pad: 0.5 pF/leg allowance; extpr adds the pad_rf_pair delta (+42/+53 fF) and Rg 150 ohm/10 um; extpp Rg 200 + pad +30 %',
                                'induced gate noise (tnoimod=1) not simulated: PDK card does not converge at the operating point; estimate +0.5-1 dB '
                                '(the pessimistic +1.5 dB derate is reported separately)',
                                'statistical transient-noise chain NF removed (superseded by tb.chain_det)',
                                'no Monte Carlo']
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
    idd_ma = nom['idd_a'] * 1e3 if nom.get('idd_a') else None
    perf = [{'metric': 'conversion gain, 300 ohm/leg source, 2.4 GHz LO, 5 MHz IF (dB)', 'target': '> 0 (arch, voltage)',
             'extracted_nominal': g, 'schematic_nominal': sch.get('conversion_gain_db'), 'pass': g is not None and g > 0},
            {'metric': 'supply current (mA)', 'target': '<= 3.1 (fork V: 2x TIA OTA; power_budget.py rxmix entry)',
             'extracted_nominal': idd_ma, 'pass': idd_ma is not None and idd_ma <= 3.1},
            {'metric': 'baseband output CM (V)', 'target': '1.65 +- 0.1', 'extracted_nominal': nom.get('vcm_v'),
             'pass': nom.get('vcm_v') is not None and abs(nom['vcm_v'] - 1.65) <= 0.1},
            {'metric': 'TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V)',
             'target': '|residual| < 10 mV referred to the filter input', 'extracted_nominal':
                 [cal_nom.get('raw_offset_v'), cal_nom.get('residual_v'), cal_nom.get('lsb_v')], 'detail': cal_nom,
             'pass': cal_nom.get('residual_v') is not None and abs(cal_nom['residual_v']) < 0.01}]
    ab = GEN / 'rxmix-ab.json'   # fork V: chain A/B rows (I/Q, IRR, out-of-band IIP3, DSB NF), scratch/rf-tia-v
    if ab.exists():
        perf += json.loads(ab.read_text())['rows']
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
                                'I/Q, IRR, out-of-band IIP3 and chain DSB NF: tt (and ss NF) only, from rxmix-ab.json; '
                                'IIP2, LO leakage not simulated', 'no Monte Carlo',
                                'chain NF OTA term recombined with fnoicor=1 en at the corner; h3/h5 folding not measured (0 by construction)']
    return rec


# ---------------------------------------------------------------- baseband filter
BW7 = ('en', 'bw0', 'bw1', 'bw2', 'bw3')   # narrowest (all 4 bandwidth bits)
def _tagc(c):
    return {'mos': c[0], 'temp_c': c[1], 'vdd_v': c[2]}


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
    import bbf_bench as BB0
    wide0 = BB0.ac(w, 'ext', NOM, block, BB0.on_for(0, 0, BB0.F.QT_RESET), tag='wide0')
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
        {'metric': 'RX -3 dB cutoff at the reset cap code 8 (bw0) and reset Q code 6 (Hz)', 'target': '~10.5e6 class (trimmed per part: CNV-01 row)',
         'extracted_nominal': rx.get('f3db_hz'), 'schematic_nominal': sch.get('f3db_hz')},
        {'metric': 'RX -3 dB cutoff, narrowest (bw=15) (Hz)', 'target': '1e5 min', 'extracted_nominal': R['rx_bw7'].get('f3db_hz')},
        {'metric': 'passband peaking at the reset codes (dB above DC)', 'target': '<= 1 dB ripple',
         'extracted_nominal': (rx['peak_gain_db'] - rx['dc_gain_db']) if rx.get('peak_gain_db') is not None else None},
        {'metric': 'PGA gain range (dB, code -6 .. 42)', 'target': '-6 .. 42 in 3 dB steps',
         'extracted_nominal': [pga[-6].get('dc_gain_db'), pga[42].get('dc_gain_db')]},
        {'metric': 'PGA code sweep, reset cap/Q codes (code dB: dc gain dB, peaking dB, f3db Hz)', 'target': '3 dB steps (+-0.5 dB), <= 1 dB ripple, cutoff independent of gain',
         'extracted_nominal': {c: [pga[c].get('dc_gain_db'), (pga[c]['peak_gain_db'] - pga[c]['dc_gain_db']) if pga[c].get('peak_gain_db') is not None else None,
                                   pga[c].get('f3db_hz')] for c in PGA_CODES}},
        {'metric': 'TX direction (tx_in -> out_tx) cutoff and gain', 'extracted_nominal': R['tx']},
        {'metric': 'gain at 20 MHz, widest cap code 0, reset Q code 6, PGA 0 dB (dB relative to DC) (40 MHz channels need ~20 MHz corner)',
         'target': '>= -3 dB (GX-1 trim row: 20..30 MHz per corner)', 'extracted_nominal': wide0.get('rel_wide_db'),
         'f3db_hz': wide0.get('f3db_hz'), 'pass': (wide0.get('rel_wide_db') or -99) >= -3.0,
         'note': 'review fix: this row previously ran the reset cap code 8'},
        {'metric': 'supply current, RX active (mA)', 'target': 'allocation 3.77 mA (analog-architecture.json); previous design 6.66 mA', 'extracted_nominal': rx['idd_a'] * 1e3 if rx.get('idd_a') else None},
        {'metric': 'output CM minus input CM with input CM at 1.75 V (V), PGA 0 / 42 dB (FD OTAs with CMFB to the input CM)',
         'target': '|x| <= 50 mV at every PGA code (no PGA-gain multiplication)', 'extracted_nominal': [cm1.get('out_cm_minus_in_cm_v'), cm16.get('out_cm_minus_in_cm_v')]},
        {'metric': 'passband peaking at max PGA gain, reset codes (dB above DC)', 'target': '<= 1 dB ripple',
         'extracted_nominal': (R['rx_g15']['peak_gain_db'] - R['rx_g15']['dc_gain_db']) if R['rx_g15'].get('peak_gain_db') is not None else None},
        {'metric': 'TX observe through bb_tap into 10 pF: -3 dB (Hz) / gain (dB) / HD3 at 0.4 and 0.8 Vpk diff (dBc)',
         'extracted_nominal': [txo[0].get('f3db_hz'), txo[0].get('lf_gain_db'), txo[1].get('hd3_dbc'), txo[2].get('hd3_dbc')]},
        {'metric': 'TX->RX direction switch settling to 1 % (s)', 'target': 1e-6, 'extracted_nominal': settle.get('settle_1pct_after_switch_s'),
         'detail': settle},
    ]
    if not quick:
        import bbf_bench as BB   # fork S: FD filter benches (CNV-01, GX-1, RC-17, DCOC-F)
        bv = BB.validate(w / 'val')   # fork B: every bench on hand-calculable circuits + deliberately broken ones
        perf.append({'id': 'bench-validation', 'metric': 'bbf_bench self-test: ideal Butterworth AC, resistor-network noise (4kTR), '
                     'op fallback detector, op/latch detector (bistable stand-in must FAIL), oscillation detector (RHP biquad must FAIL)',
                     'target': 'every check reproduces its analytic answer and every broken case fails', 'pass': bv.get('state') == 'pass', 'detail': bv})
        QC = [('ff', 22, 3.35), ('typical', 27, 3.3), ('ss', 32, 3.15)]
        qcodes = (0, 3, 6, 9, 12, 15)
        qjobs = [(c, g, q) for c in QC for g in (0, 42) for q in qcodes]
        qres = par([(lambda c=c, g=g, q=q: BB.ac(w, 'ext', c, block, BB.on_for(g, 0, q), tag=f'qtw_g{g}q{q}')) for c, g, q in qjobs])
        perf.append({'metric': 'Q-trim code sweep (qt 0..15, 6 shown), PGA 0 / 42 dB, widest cap code 0: peaking dB, f3db Hz',
                     'rows': [{'corner': _tagc(c), 'pga_db': g, 'qt': q, 'peaking_db': r.get('peaking_db'),
                               'f3db_hz': r.get('f3db_hz'), 'error': r.get('error')} for (c, g, q), r in zip(qjobs, qres)]})
        cnv = par([(lambda c=c: dict(corner=_tagc(c), **BB.trim_cnv01_pga(w / 'cnv', 'ext', c, block))) for c in CORNERS])
        perf.append({'id': 'CNV-01', 'metric': 'Wi-Fi 20 MHz at 40 MS/s: per-corner trim (cap code m: bw = m>>3, fc_fine = m&7; Q code) '
                     'and a per-PGA-code cap-code offset table (FS-1), checked at EVERY PGA code -6..42 dB: f3 = 10.5 +- 0.5 MHz, '
                     'droop <= 3 dB at 8.75 MHz, >= 38 dB at 31.25 MHz (alternate-channel alias), peaking <= 1 dB',
                     'target': 'pass at all 12 envelope corners x 17 PGA codes',
                     'pass': all(r.get('state') == 'pass' for r in cnv), 'rows': cnv,
                     'note': 'review fix: a single trim gave 9.41-9.58 MHz at PGA 42 dB (stage-1 noise gain 1 + k/4 and the '
                             '+12 dB biquad steps lower the cutoff ~8 %); the offset table is part of the per-part calibration'})
        wide = par([(lambda c=c: dict(corner=_tagc(c), **BB.trim_wide(w / 'wide', 'ext', c, block))) for c in CORNERS])
        perf.append({'id': 'GX-1', 'metric': 'wide range: per-corner cap code (0..7) and a Q code per coarse PGA state (0 / 21 / 42 dB shown) '
                     'with f3 in 20..30 MHz, peaking <= 1 dB, droop <= 3 dB at 19.1 MHz', 'target': 'pass at all 12 envelope corners',
                     'pass': all(r.get('state') == 'pass' for r in wide), 'rows': wide})
        g42 = par([(lambda c=c: dict(corner=_tagc(c), **BB.ac(w / 'g42', 'ext', c, block, BB.on_for(42, 0, 15), tag='g42w'))) for c in CORNERS])
        perf.append({'id': 'RC-17', 'metric': 'PGA 42 dB, widest cap code 0, Q code 15: f3db Hz, peaking dB',
                     'target': 'f3db >= 10 MHz at every corner (and the trimmed CNV-01 / GX-1 rows above hold at 42 dB)',
                     'pass': all((r.get('f3db_hz') or 0) >= 10e6 for r in g42), 'rows': g42})
        C3 = [('typical', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ss', 22, 3.35), ('ff', 32, 3.15)]
        opp = par([(lambda c=c: dict(corner=_tagc(c), **BB.op_dc(w / 'op', 'ext', c, block))) for c in C3])
        pup = par([(lambda c=c: dict(corner=_tagc(c), **BB.powerup(w / 'pu', 'ext', c, block))) for c in C3])
        perf.append({'id': 'RC-17', 'metric': 'PGA 42 dB, input CM 1.75 V: DC operating point. ngspice gmin/source homotopies do NOT converge '
                     'on this netlist (seed = pseudo-transient); proof of a DC solution = plain Newton re-solve from a .nodeset of the seed '
                     '(no homotopy, no fallback, <= 10 mV from the seed on the signal nodes); latch search = transients (uic) from 4 extreme '
                     'initial states (CM 0.3 / 3.0 V, +-1 V DM on every stage output and OTA first-stage node) that must settle to the same state',
                     'target': 'Newton-verified DC solution, unique across the 4 starts (+-10 mV), output CM = input CM +- 50 mV',
                     'pass': all(r.get('state') == 'pass' for r in opp), 'rows': opp,
                     'note': 'review fix: the fork-S row claimed plain Newton but every log showed "Transient op started"; bench self-test: bench-validation row (a bistable stand-in fails)'})
        perf.append({'id': 'RC-17', 'metric': 'PGA 42 dB, reset cap/Q codes (8 / 6), input CM 1.75 V: supply + controls ramp 0 -> final in 2 us; output at 18..20 us',
                     'target': 'no latch: output CM = input CM +- 50 mV, |diff| < 0.1 V, no oscillation',
                     'pass': all(r.get('state') == 'pass' for r in pup), 'rows': pup})
        # fork B (review item 1): every coarse PGA state x the validator boundary (m <= 1: qt >= 6) and cap codes >= 2 at
        # the highest-Q code qt 0, at the worst skew (slow MOS / fast R-MIM, 32 C), spot checks at the other skews
        KJ = sorted(set([(1, g, m, q) for m in (0, 1) for q in (6, 15) for g in (0, 21, 42)]
                        + [(1, g, m, q) for m in (2, 4, 16) for q in (0, 15) for g in (0, 42)]
                        + [(0, 0, 0, 6), (0, 42, 0, 6), (0, 0, 2, 0), (0, 42, 2, 0), (2, 0, 0, 6), (2, 42, 0, 6),
                           (2, 0, 2, 0), (2, 42, 2, 0), (3, -6, 127, 0), (3, 42, 0, 6), (6, -6, 127, 0), (1, -6, 127, 0),
                           (5, 0, 0, 6), (4, 42, 0, 6), (1, 0, 0, 0), (1, 42, 0, 0)]))
        kik = par([(lambda si=si, g=g, m=m, q=q: dict(pga_db=g, cap_code=m, qt=q, **BB.kick(w / 'kick', 'ext', BB.SKEW[si], BB.on_for(g, m, q))))
                   for si, g, m, q in KJ])
        perf.append({'id': 'RC-17', 'metric': 'stability, every validator-allowed combination: kick (20 mV, 10 ns) + held +100 mV input-CM step '
                     'transient at SKEWED corners (MOS and poly-R/MIM corners independent, poly sheet +-25 %: design-assumptions.md); '
                     'every stage DM and CM (s1, bp1, lp1, bp2, co) residual at 5-6 us. Worst cases by construction: lowest cap code '
                     '(highest integrator frequency, lowest OTA feedback factor) at the highest allowed Q (validator: cap code <= 1 '
                     'requires qt >= 6; qt 0 also run), every coarse PGA state (0/21/42 dB); cap codes 2/4/16 at qt 0 and 15; cap code 127 at PGA -6 dB (highest feedback factor)',
                     'target': 'every residual < 50 uV or decaying (no sustained / growing oscillation)',
                     'pass': all(r.get('state') == 'pass' for r in kik), 'rows': kik,
                     'note': 'review fix (scratch/review-bbf): the fork-S design oscillated at ss MOS / fast R-MIM, cap code 0, qt 12 '
                             '(2.47 V pp, 31 MHz). AC phase-sign screen over the full cap x Q x PGA grid: scratch/rf-bbf-u/gridx3.out'})
        dc = par([(lambda c=c: dict(corner=_tagc(c), **BB.dcoc(w / 'dcoc', 'ext', c, block))) for c in C3[:3]])
        perf.append({'id': 'DCOC-F', 'metric': 'fine DC-offset DAC (sign + 8 bits into the stage-1 summing nodes): stage-1 output step, range, monotonicity',
                     'target': 'LSB < 1 mV at the stage-1 output (<= ~1 % ADC FS at 42 dB), range > +-80 mV, monotonic',
                     'pass': all(r.get('state') == 'pass' for r in dc), 'rows': dc})
        nz = par([(lambda c=c, g=g: dict(corner=_tagc(c), **BB.noise(w / 'nz', 'ext', c, block, g, 8, BB.F.QT_RESET)))
                  for c in (NOM, ('ss', 32, 3.15)) for g in (0, 6, 12, 18, 21, 30, 42)])
        CREF = BB.chain_ref()
        CHAIN_NF_DSB_DB = round(CREF['nf_dsb_db']['tt'], 3)
        for r in nz:
            nf0 = CREF['nf_dsb_db']['ss' if r['corner'].get('mos') == 'ss' else 'tt']
            r['chain_nf_dsb_db_no_filter'] = round(nf0, 3)
            r['chain_nf_dsb_db_with_filter'] = 10 * __import__('math').log10(10 ** (nf0 / 10) + r['delta_f_at_5mhz']) if r.get('delta_f_at_5mhz') is not None else None
        tt_nz = [r for r in nz if r['corner'] == _tagc(NOM)]
        agc = min((r['pga_db'] for r in nz if r.get('chain_nf_dsb_db_with_filter') is not None
                   and r['chain_nf_dsb_db_with_filter'] - r['chain_nf_dsb_db_no_filter'] <= 0.3
                   and all(q['chain_nf_dsb_db_with_filter'] - q['chain_nf_dsb_db_no_filter'] <= 0.3 for q in nz
                           if q['pga_db'] == r['pga_db'] and q.get('chain_nf_dsb_db_with_filter') is not None)), default=None)
        perf.append({'id': 'RF-RX-NF', 'metric': 'filter noise (PGA code, reset cap/Q codes): input-referred density at 1 / 5 MHz, output rms '
                     '0.1-10 MHz, and the chain NF with the filter (F_chain + (v_in,filter / v_src at the filter input)^2; LNA + mixer '
                     f'gain {BB.CHAIN_GAIN_DB} dB, DSB source noise at the filter input {BB.chain_source_noise_v() * 1e9:.0f} nV/rtHz, '
                     f'chain NF without the filter {CHAIN_NF_DSB_DB} dB DSB tt / {CREF["nf_dsb_db"]["ss"]:.3f} ss (read at run time from generated/rf_rx_chain.json); AGC row = lowest PGA code meeting <= 0.3 dB at BOTH tt and ss)',
                     'target': 'AGC requirement: the PGA code at sensitivity keeps the filter penalty <= 0.3 dB',
                     'agc_min_pga_db_for_0p3db': agc, 'chain_reference': CREF, 'pass': agc is not None and agc <= 21, 'rows': nz,
                     'note': 'review fix: noise was not characterised; at PGA 0 dB the filter adds several dB, so the AGC holds the PGA '
                             'at or above agc_min_pga_db_for_0p3db until the input is well above sensitivity'})
        perf.append({'metric': 'corner sweep (ext, RX reset cap code 8 (bw0), gain 0, reset Q code)', 'rows': corner_table(
            lambda c: tb.bbf_ac(w, 'ext', c, block, tag='rx'), ['f3db_hz', 'dc_gain_db', 'peak_gain_db', 'idd_a', 'out_cm_v'])})
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
    rec['excluded_coverage'] = ['fully differential 5th-order Butterworth (stage-1 real pole + 2 Tow-Thomas biquads), FD two-stage OTAs with '
                                'continuous CMFB to atb_vcm (fork S, bbf_fd.py); cutoff: cap code 0..127 (bw0..3 coarse x 8 + fc_fine0..2), '
                                'Q: 4-bit qt (Q = q_top (1 - 0.032 k), reset 6), both set per part at bring-up (trim rows above are the per-corner codes)',
                                'PGA -6..42 dB: stage-1 conductance k/4 (6 bits) x two +12 dB biquad steps (gainc0/1); netlists.GAIN_TABLE',
                                'narrowest corner limited by the capacitor bank (~1.2 MHz): LoRa 203/406 kHz needs a lower cutoff: open',
                                'noise: rows above (filter alone + chain-NF penalty); linearity only via the TX-observe HD3 points',
                                'validator rule (FS-1): cap code <= 1 requires qt >= 6 (stability margin at the highest integrator frequency)',
                                'no Monte Carlo (CMFB and DCOC range cover mismatch offsets by design, not verified statistically)',
                                'trim search is per corner on the extracted netlist; a production calibration routine (inject + observe) is not modelled']
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
        [f'MXS{i} b off a 0 nfet_06v0 w=10u l=0.7u' for i in range(2 * N.TAP_OBS_M)] +
        [f'MXJ{i} a off b 0 nfet_06v0 w=10u l=0.7u' for i in range(2 * N.TAP_INJ_M)]), 20e6)
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
                          're-driven from the island rail so it is 0 V whenever the island is off. PD29: pad-facing '
                          'switches are nfet_06v0 whose gates sit behind ~%g kohm poly with a ~%g fF gate-to-pad MIM, so '
                          'the gates track the pad under HBM; core-gate HBM screen: pads/hbm_core_screen.py bb_tap wmon_bb_tap.'
                          % (N.TAP_RG_INJ or N.TAP_RG, round(2 * N.TAP_CC ** 2))},
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
    import lna_match as LM
    m = LM.board_trim_nominal(w / 'bt', 'ext', NOM)     # RC-16h: the board trimmer network (was an ideal L-match)
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
    # fork P: the statistical transient-noise chain NF (+-1.5 dB, produced physically impossible values) is
    # superseded by tb.chain_det and no longer run; tn_job is kept for manual use.
    # deterministic chain NF (tb.chain_det): extracted LNA + pad_rf_pair + Rg 150 ohm/10 um, board match at reset ct
    # fork P: board network = the per-board ladder fitted at that corner (lna_match.per_board), ct inside 4..10
    def det_job(c, sub):
        def job():
            import lna_match as LM
            m = LM.board_trim_nominal(w / sub, 'extpr', c)      # RC-16h board trimmer network, tuned for this corner
            return tb.chain_det(w / sub, 'extpr', c, ct=m['ct'], match=m, rt=bool(m['rt']))
        return job
    jobs['det_lna_matched_extpr'] = det_job(NOM, 'det')
    if not quick:
        jobs['det_lna_matched_extpr_ss_32_3.15'] = det_job(('ss', 32, 3.15), 'det_ss')
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
