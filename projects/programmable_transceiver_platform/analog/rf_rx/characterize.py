"""Run the mixer / baseband-filter / bb_tap testbenches and the RF chain points of the RF receive family and write
generated/<block>-evidence.json and generated/rf_rx_chain.json.

Usage:  python3 characterize.py [--quick] [--jobs N] [--corners full|reduced|min] [--blocks chain rxmix_i rxmix_q bb_tap ...]
  --quick    nominal points only (no corner sweeps, chain: the matched point only)
  --corners  rxmix / bb_tap corner sweeps: full = tt/ss/ff/sf/fs x 22/32 C x 3.15/3.35 V (20, simlib.CORNERS_5P);
             reduced = every process at 32 C / 3.15 V and 22 C / 3.35 V (10); min = every process at 32 C / 3.15 V (5).
             The set that was run is recorded in the evidence ('corner_set').  bbfilter keeps its 12-point tt/ss/ff list.

The LNA is NOT characterised here: its evidence (generated/lna-evidence.json) is written by lna_close.py
(python3 lna_close.py currents | stab | stab_lf | band | chain | neg | write).  `--blocks lna` prints that and does nothing.

Nothing here regenerates a layout; the layout records generated/<block>-layout.json are read and compared with the
files on disk (sha256).  States:
  tests.clean          Magic DRC = 0, Netgen unique match, layout record = files on disk, extracted nominal basic function
  performance_state    'fail' if any performance row has pass = False (corner rows included), 'open' if a row could not be
                       evaluated ('not available'), else 'pass'.  failing_rows lists them.
Chain rows (I/Q balance, chain NF) are only used when they were measured on the extracted netlists now on disk
(sha256 for rf_rx_chain.json; hashes / file times for the lna_close.py chain points); otherwise the row says 'not available'.
"""
import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor

import rfrx_flow as flow
import simlib as S
import tb

HERE = flow.HERE
import netlists as N  # noqa: E402
GEN = flow.GENERATED
WORK = flow.SCRATCH / 'char'
NOM = ('typical', 27, 3.3)
SS_PESS = ('ss', 32, 3.15)
BBF_CORNERS = S.CORNERS            # bbfilter: the 12-point list its published evidence was swept on
CORNER_SETS = {'full': S.CORNERS_5P,
               'reduced': [c for c in S.CORNERS_5P if (c[1], c[2]) in ((32, 3.15), (22, 3.35))],
               'min': [c for c in S.CORNERS_5P if (c[1], c[2]) == (32, 3.15)]}
CORNER_SET = 'full'
CORNERS = CORNER_SETS[CORNER_SET]  # rxmix / bb_tap sweeps (set in main)
NA = 'not available'
POOL = None
CHAIN_CELLS = ('lna', 'rxmix_i', 'rxmix_q')
LNA_MSG = ('lna: not characterised by characterize.py.  The LNA evidence (generated/lna-evidence.json) is written by lna_close.py: '
           'python3 lna_close.py currents | stab | stab_lf | band | chain | neg | write.  Skipped, nothing written.')


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


def record_vs_disk(lay):
    """Compare the layout record's sha256 entries with the files on disk.  cell = the block's own netlist and layout
    artefacts (gating); generators = scripts that write every block (information: they change when another block changes)."""
    cell, gen = [], []
    block = lay['block']
    for k, v in {**lay.get('sources', {}), **lay.get('artifacts', {})}.items():
        p = HERE / k if (HERE / k).exists() else GEN / k
        now = flow.sha256(p) if p.exists() else None
        if now != v:
            (cell if k.startswith(block) else gen).append(k)
    return dict(cell_files_differ=cell, generator_scripts_changed_since_layout=gen, matches_disk=not cell)


def clean_state(lay, nominal_ok):
    ok = lay['drc_count'] == 0 and lay['lvs']['unique_match'] and nominal_ok and record_vs_disk(lay)['matches_disk']
    return 'pass' if ok else 'fail'


def base_record(block, lay):
    return {
        'block': block,
        'top_cell': f'pt_{block}',
        'source_hashes': {k: v for k, v in lay['sources'].items()},
        'artifact_hashes': lay['artifacts'],
        'simulated_netlist_sha256': {f'{block}.ext.spice': flow.sha256(GEN / f'{block}.ext.spice'),
                                     f'{block}.spice': flow.sha256(HERE / f'{block}.spice')},
        'layout_record_vs_disk': record_vs_disk(lay),
        'images': {'analog': flow.ANALOG_IMAGE, 'analog_ref': flow.ANALOG_REF,
                   'digital': flow.DIGITAL_IMAGE, 'digital_tag': flow.DIGITAL_TAG},
        'pdk': 'gf180mcuD; ' + flow.PDK_NOTE,
        'extraction': 'capacitance only (Magic ext2spice); wire and via resistance NOT extracted',
        'area': {'bbox_um': lay['bbox_um'], 'area_um2': lay['area_um2']},
    }


def drc_lvs(lay):
    return ({'tool': 'Magic 8.3.623 drc(full), euclidean', 'errors': lay['drc_count'],
             'error_tiles': lay['drc_raw'], 'report': f"generated/{lay['block']}-layout.json",
             'klayout_crosscheck': lay.get('klayout_drc')},
            {'tool': 'Netgen 1.5.316 gf180mcuD_setup.tcl', 'result': lay['lvs']['final_result'],
             'unique_match': lay['lvs']['unique_match'], 'report': f"generated/{lay['block']}-lvs.txt"})


def _tagc(c):
    return {'mos': c[0], 'temp_c': c[1], 'vdd_v': c[2]}


def corner_table(fn, keys, corners=None):
    rows = par([lambda c=c: dict(corner=_tagc(c), **fn(c)) for c in (CORNERS if corners is None else corners)])
    return [{k: r.get(k) for k in ['corner', 'error'] + keys if k in r} for r in rows]


def corner_pass(rows, checks):
    """Mark every corner row: checks = {name: predicate(row)}; a failed run or a missing value is a failed row.
    Returns (all rows pass, {check: number of failing rows})."""
    bad = {k: 0 for k in checks}
    for r in rows:
        res = {}
        for k, fn in checks.items():
            try:
                res[k] = bool('error' not in r and fn(r))
            except (TypeError, KeyError):
                res[k] = False
            bad[k] += not res[k]
        r['pass'] = all(res.values())
        if not r['pass']:
            r['failed_checks'] = [k for k, v in res.items() if not v]
    return bool(rows) and all(r['pass'] for r in rows), bad


def corner_note():
    cs = CORNERS
    return (f"corner set '{CORNER_SET}': {len(cs)} points, MOS {sorted(set(c[0] for c in cs))} x "
            f"T/V {sorted(set((c[1], c[2]) for c in cs))}" + ('' if CORNER_SET == 'full' else ' (REDUCED set: not the full 20-point envelope)'))


def finish(rec, perf, corners=None, name=None):
    """Every row carries a pass field (True / False / 'info' / 'not available'); the record carries the aggregate."""
    for r in perf:
        r.setdefault('pass', 'info')
    failing = [r['metric'][:110] for r in perf if r['pass'] is False]
    na = [r['metric'][:110] for r in perf if r['pass'] == NA]
    rec['performance_vs_target'] = perf
    rec['performance_state'] = 'fail' if failing else ('open' if na else 'pass')
    rec['failing_rows'] = failing
    rec['rows_not_available'] = na
    rec['corner_set'] = {'name': name or CORNER_SET, 'corners': [_tagc(c) for c in (CORNERS if corners is None else corners)]}
    return rec


# ---------------------------------------------------------------- chain references (current cells only)
def cell_hashes():
    return {f'{b}.ext.spice': flow.sha256(GEN / f'{b}.ext.spice') for b in CHAIN_CELLS}


def load_chain():
    """generated/rf_rx_chain.json if it was measured on the extracted netlists now on disk, else (None, reason)."""
    p = GEN / 'rf_rx_chain.json'
    if not p.exists():
        return None, 'generated/rf_rx_chain.json does not exist'
    try:
        d = json.loads(p.read_text())
    except ValueError as e:
        return None, f'generated/rf_rx_chain.json unreadable: {e!r}'[:200]
    if d.get('netlist_sha256') != cell_hashes():
        return None, ('generated/rf_rx_chain.json was not measured on the lna / rxmix_i / rxmix_q extracted netlists now on disk '
                      '(sha256 differ or not recorded): stale')
    return d, None


def chain_nf_rows():
    """Deterministic chain-NF points of lna_close.chain_point (real channel, LO as delivered) IF they belong to the cells on
    disk.  Source 1: generated/lna-evidence.json tests.chain_nf, bound by its 'hashes' entry for lna.ext.spice and newer than
    both mixer netlists.  Source 2: scratch/rf_rx/close/chain.json, newer than all three extracted netlists.
    Returns (rows, source) or (None, reason).  Never a number from an older LNA."""
    ext = {b: GEN / f'{b}.ext.spice' for b in CHAIN_CELLS}
    newest = lambda bs: max(ext[b].stat().st_mtime for b in bs)
    why = []
    p = GEN / 'lna-evidence.json'
    try:
        ev = json.loads(p.read_text())
        rows = ((ev.get('tests') or {}).get('chain_nf') or {}).get('rows')
        if not rows:
            why.append('lna-evidence.json has no chain_nf rows')
        elif 'sha256:' + str((ev.get('hashes') or {}).get('lna.ext.spice')) != flow.sha256(ext['lna']):
            why.append('lna-evidence.json describes another lna.ext.spice than the one on disk (sha256)')
        elif p.stat().st_mtime < newest(('rxmix_i', 'rxmix_q')):
            why.append('lna-evidence.json is older than the mixer netlists on disk')
        else:
            return rows, 'generated/lna-evidence.json tests.chain_nf (lna_close.py, sha256-bound to lna.ext.spice on disk)'
    except (OSError, ValueError) as e:
        why.append(f'lna-evidence.json unreadable: {e!r}'[:120])
    p = flow.SCRATCH / 'close' / 'chain.json'
    try:
        rows = json.loads(p.read_text())
        if p.stat().st_mtime < newest(CHAIN_CELLS):
            why.append('scratch/rf_rx/close/chain.json is older than the extracted netlists on disk')
        elif not isinstance(rows, list) or not rows:
            why.append('scratch/rf_rx/close/chain.json has no rows')
        else:
            return rows, 'scratch/rf_rx/close/chain.json (lna_close.chain_point; newer than the three extracted netlists on disk)'
    except (OSError, ValueError):
        why.append('scratch/rf_rx/close/chain.json does not exist or is unreadable')
    return None, '; '.join(why)


def _corner_is(r, c):
    return list(r.get('corner') or []) == list(c)


def chain_reference():
    """LNA + mixer/TIA reference for the filter's chain-NF penalty row: DSB chain NF and source-EMF -> I baseband gain at
    5 MHz (mean of the 4 / 6 MHz tones) of the lna_close chain points, tt (extpr nominal) and ss (extpr ss 32 C 3.15 V).
    Values are None with the reason when no chain point of the current cells exists (no pinned fallback)."""
    rows, src = chain_nf_rows()
    out = dict(nf_dsb_db={'tt': None, 'ss': None}, gain_db_by={'tt': None, 'ss': None}, lo={'tt': None, 'ss': None},
               available=False, source=src)
    if rows is None:
        return out
    for k, c in (('tt', NOM), ('ss', SS_PESS)):
        r = next((r for r in rows if r.get('view') == 'extpr' and _corner_is(r, c) and r.get('nf_dsb_db') is not None), None)
        g = (r or {}).get('gain_sig_db') or {}
        if r and g.get('4.0MHz') is not None and g.get('6.0MHz') is not None:
            out['nf_dsb_db'][k] = r['nf_dsb_db']
            out['gain_db_by'][k] = round((g['4.0MHz'] + g['6.0MHz']) / 2, 2)
            out['lo'][k] = r.get('lo')
    out['available'] = all(v is not None for v in out['nf_dsb_db'].values())
    return out


# ---------------------------------------------------------------- mixers
RXMIX_IDD_RX_MA, RXMIX_IDD_DUPLEX_MA, RXMIX_RESIDUAL_V, CHAIN_NF_DSB_DB_MAX = 6.2, 3.1, 0.01, 4.1


RXMIX_ONE_STATE = ('supply current (mA); the cell has no hib pin (netlists.OTAN_XTAIL off): one state serves RX and duplex',
                   'supply current / conversion gain against the duplex limit (mA, dB): the SAME run as the row above (no hib pin, '
                   'no separate duplex state); not an independent measurement')


def chain_rows_for_mixer():
    """Chain-level rows of the mixer evidence, from the current cells only (else 'not available')."""
    rows = []
    chain, why = load_chain()
    cm = (chain or {}).get('ext_m')
    irr = {'metric': 'chain I/Q gain mismatch (dB) / phase error (deg) / image rejection (dB), uncorrected: extracted LNA (extpr) + rxmix_i + '
                     'rxmix_q on the real COB channel with per-chip carrier parts, tt 27 C 3.3 V, tone at LO + 5 MHz, ideal square LO '
                     '(tb.chain_tran; generated/rf_rx_chain.json)',
           'target': 'RF-RX-IRR >= 25 dB uncorrected'}
    if isinstance(cm, dict) and cm.get('irr_db') is not None:
        irr.update(extracted_nominal=[cm.get('iq_gain_mismatch_db'), cm.get('iq_phase_error_deg'), cm.get('irr_db')],
                   chain_gain_db=[cm.get('gain_i_db'), cm.get('gain_q_db')], **{'pass': cm['irr_db'] >= 25.})
    else:
        irr.update(extracted_nominal=None, note=why or f"chain point ext_m failed or was not run: {str((cm or {}).get('error'))[-200:]}",
                   **{'pass': NA})
    rows.append(irr)
    nfr, src = chain_nf_rows()
    nf = {'metric': 'chain NF, DSB (dB): deterministic multitone bench (tb.chain_det via lna_close.chain_point), extracted LNA + both '
                    'mixers, real COB channel with lossy per-chip carrier parts, LO as delivered (tb.LO_REAL)',
          'target': f'on-chip <= {CHAIN_NF_DSB_DB_MAX} dB DSB at every row (RF-RX-NFSYS 8 dB - 3.91 dB board budget)'}
    if nfr is None:
        nf.update(extracted_nominal=None, note=f'{NA} for the cells on disk: {src}', **{'pass': NA})
    else:
        t = next((r for r in nfr if r.get('view') == 'extpr' and _corner_is(r, NOM)), {})
        nf.update(extracted_nominal=t.get('nf_dsb_db'), source=src,
                  points=[{k: r.get(k) for k in ('view', 'corner', 'lo', 'lo_level', 'nf_dsb_db', 'nf_ssb_db', 'gain_sig_db')} for r in nfr],
                  **{'pass': all(r.get('nf_dsb_db') is not None and r['nf_dsb_db'] <= CHAIN_NF_DSB_DB_MAX for r in nfr)})
    rows.append(nf)
    lin = GEN / 'rf_rx_linearity.json'
    ip3 = {'metric': 'chain out-of-band IIP3 (dBm), two tones at LO+20/+37 MHz, IM3 at 3 MHz, extracted LNA + mixers, tt '
                     '(linearity.py; generated/rf_rx_linearity.json)', 'target': 'RF-RX-IIP3 >= -10 dBm'}
    lj = json.loads(lin.read_text()) if lin.exists() else {}
    if lj.get('netlist_sha256') == cell_hashes():
        ip = [r for r in lj['results'] if r.get('mode') == 'iip3']
        ip3.update(extracted_nominal=[[r['p_dbm'], r['iip3_dbm']] for r in ip], detail=lj['results'],
                   **{'pass': bool(ip) and all(r['iip3_dbm'] >= -10. for r in ip if r['p_dbm'] <= -40.)})
    else:
        ip3.update(extracted_nominal=None, **{'pass': NA},
                   note=f'{NA}: generated/rf_rx_linearity.json was not measured on the extracted netlists now on disk (stale or absent)')
    rows.append(ip3)
    return rows


def do_rxmix(block, quick):
    w = WORK / block
    lay = layout(block)
    lo_tt, lo_ss = 'ext_best_1v16', 'cml_1v05'
    nom, sch, off, unp27, unp85, unp0, tri, on_dc, dup, cal_nom, real_tt = par([
        lambda: tb.rxmix_tran(w, 'ext', NOM, block), lambda: tb.rxmix_tran(w, 'sch', NOM, block),
        lambda: tb.rxmix_dc(w, 'ext', block, 3.3, 0), lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 27, 3.63),
        lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 85, 3.63), lambda: tb.rxmix_dc(w, 'ext', block, 0, 1, 0, 3.63),
        lambda: tb.rxmix_dc(w, 'ext', block, 3.3, 0, 27, 0.0, vbb=1.65),
        lambda: tb.rxmix_dc(w, 'ext', block, 3.3, 1),
        # duplex state (hib = 0): base TIA OTA tail only.  Without the pin (netlists.OTAN_XTAIL off) the cell has ONE state
        (lambda: tb.rxmix_tran(w, 'ext', NOM, block, hib=False)) if tb.HIBP else (lambda: {'same_run_as_rx_state': True}),
        lambda: tb.rxmix_calibrate(w, 'ext', NOM, block),
        lambda: tb.rxmix_tran(w, 'ext', NOM, block, lo=tb.LO_REAL[lo_tt])])
    real_ss = {} if quick else par([lambda: tb.rxmix_tran(w, 'ext', SS_PESS, block, lo=tb.LO_REAL[lo_ss])])[0]
    cal = [] if quick else corner_table(lambda c: tb.rxmix_calibrate(w, 'ext', c, block), ['raw_offset_v', 'lsb_v', 'code', 'residual_v'])
    if not tb.HIBP:
        dup = dict(nom)
    g = nom.get('conversion_gain_db')
    rec = base_record(block, lay)
    d, l = drc_lvs(lay)
    idd_ma = nom['idd_a'] * 1e3 if nom.get('idd_a') else None
    gr = [real_tt.get('conversion_gain_db'), real_ss.get('conversion_gain_db')]
    perf = [{'metric': 'conversion gain, 300 ohm/leg source, 2.4 GHz ideal square LO, 5 MHz IF (dB)', 'target': '> 0 (arch, voltage)',
             'extracted_nominal': g, 'schematic_nominal': sch.get('conversion_gain_db'), 'pass': g is not None and g > 0,
             **({'error': nom['error']} if 'error' in nom else {})},
            {'metric': 'same with the LO as delivered (differential sine on 2.44 V, tb.LO_REAL): tt 27 C 3.3 V at +-0.37 V '
                       f'({lo_tt}) / ss 32 C 3.15 V at +-0.26 V ({lo_ss}) (dB)', 'target': '> 0 (arch, voltage)',
             'extracted_nominal': gr, 'loss_vs_ideal_square_lo_tt_db': (g - gr[0]) if None not in (g, gr[0]) else None,
             'supply_ma': [x['idd_a'] * 1e3 if x.get('idd_a') else None for x in (real_tt, real_ss)],
             'errors': [x.get('error') for x in (real_tt, real_ss) if x.get('error')],
             'note': 'ss point not run with --quick' if quick else None,
             'pass': all(x is not None and x > 0 for x in (gr[:1] if quick else gr))},
            {'metric': 'supply current, RX state (hib = 1: extra TIA OTA tail on) (mA)' if tb.HIBP else RXMIX_ONE_STATE[0],
             'target': f'<= {RXMIX_IDD_RX_MA} (power_budget.py RF_EVIDENCE_MA rxmix 6.11)',
             'extracted_nominal': idd_ma, 'pass': idd_ma is not None and idd_ma <= RXMIX_IDD_RX_MA},
            {'metric': 'supply current / conversion gain, duplex state (hib = 0: base tail 1.2 mA each) (mA, dB)' if tb.HIBP else RXMIX_ONE_STATE[1],
             'target': f'<= {RXMIX_IDD_DUPLEX_MA} mA (power_budget.py RXMIX_DUPLEX_MA); gain within 1 dB of the RX state',
             'extracted_nominal': [dup['idd_a'] * 1e3 if dup.get('idd_a') else None, dup.get('conversion_gain_db')],
             'pass': bool(dup.get('idd_a')) and dup['idd_a'] * 1e3 <= RXMIX_IDD_DUPLEX_MA and g is not None
                     and dup.get('conversion_gain_db') is not None and abs(dup['conversion_gain_db'] - g) <= 1.0},
            {'metric': 'baseband output CM (V)', 'target': '1.65 +- 0.1', 'extracted_nominal': nom.get('vcm_v'),
             'pass': nom.get('vcm_v') is not None and abs(nom['vcm_v'] - 1.65) <= 0.1},
            {'metric': 'TIA output offset raw / after FPGA calibration with the offset DAC (V); DAC LSB (V)',
             'target': '|residual| < 10 mV referred to the filter input', 'extracted_nominal':
                 [cal_nom.get('raw_offset_v'), cal_nom.get('residual_v'), cal_nom.get('lsb_v')], 'detail': cal_nom,
             'pass': cal_nom.get('residual_v') is not None and abs(cal_nom['residual_v']) < RXMIX_RESIDUAL_V}]
    perf += chain_rows_for_mixer()
    if cal:
        ok, bad = corner_pass(cal, {'residual_lt_10mv': lambda r: abs(r['residual_v']) < RXMIX_RESIDUAL_V})
        perf.append({'metric': 'offset calibration across the envelope (ext; calibrated at each point)',
                     'target': '|residual| < 10 mV at every corner', 'corners': corner_note(), 'pass': ok, 'failing_rows_by_check': bad, 'rows': cal})
    if not quick:
        sweep = corner_table(lambda c: tb.rxmix_tran(w, 'ext', c, block), ['conversion_gain_db', 'idd_a', 'bb_offset_v', 'vcm_v'])
        ok, bad = corner_pass(sweep, {'gain_gt_0_db': lambda r: r['conversion_gain_db'] > 0,
                                      'idd_rx_le_limit': lambda r: r['idd_a'] * 1e3 <= RXMIX_IDD_RX_MA})
        perf.append({'metric': 'corner sweep (ext transient, ideal square LO): conversion gain, supply current, raw offset, output CM',
                     'target': f'every corner: conversion gain > 0 dB and supply current <= {RXMIX_IDD_RX_MA} mA (the nominal limits applied '
                               'at every corner, as for the LNA currents)',
                     'corners': corner_note(), 'pass': ok, 'failing_rows_by_check': bad, 'rows': sweep})
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
    rec['excluded_coverage'] = ['corner sweeps and the nominal rows use an ideal 0/VDD 50 % square LO; the LO as delivered is covered by two points only '
                                '(quadrature block output not co-simulated)',
                                'IRR: tt only, ideal square LO; IIP2, LO leakage not simulated',
                                'extraction is capacitance-only (no wire / via resistance)',
                                'no Monte Carlo (IRR excludes device mismatch)']
    return finish(rec, perf)


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
        cnv = par([(lambda c=c: dict(corner=_tagc(c), **BB.trim_cnv01_pga(w / 'cnv', 'ext', c, block))) for c in BBF_CORNERS])
        perf.append({'id': 'CNV-01', 'metric': 'Wi-Fi 20 MHz at 40 MS/s: per-corner trim (cap code m: bw = m>>3, fc_fine = m&7; Q code) '
                     'and a per-PGA-code cap-code offset table (FS-1), checked at EVERY PGA code -6..42 dB: f3 = 10.5 +- 0.5 MHz, '
                     'droop <= 3 dB at 8.75 MHz, >= 38 dB at 31.25 MHz (alternate-channel alias), peaking <= 1 dB',
                     'target': 'pass at all 12 envelope corners x 17 PGA codes',
                     'pass': all(r.get('state') == 'pass' for r in cnv), 'rows': cnv,
                     'note': 'review fix: a single trim gave 9.41-9.58 MHz at PGA 42 dB (stage-1 noise gain 1 + k/4 and the '
                             '+12 dB biquad steps lower the cutoff ~8 %); the offset table is part of the per-part calibration'})
        wide = par([(lambda c=c: dict(corner=_tagc(c), **BB.trim_wide(w / 'wide', 'ext', c, block))) for c in BBF_CORNERS])
        perf.append({'id': 'GX-1', 'metric': 'wide range: per-corner cap code (0..7) and a Q code per coarse PGA state (0 / 21 / 42 dB shown) '
                     'with f3 in 20..30 MHz, peaking <= 1 dB, droop <= 3 dB at 19.1 MHz', 'target': 'pass at all 12 envelope corners',
                     'pass': all(r.get('state') == 'pass' for r in wide), 'rows': wide})
        g42 = par([(lambda c=c: dict(corner=_tagc(c), **BB.ac(w / 'g42', 'ext', c, block, BB.on_for(42, 0, 15), tag='g42w'))) for c in BBF_CORNERS])
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
        # chain reference: the lna_close.py chain points of the cells on disk (chain_reference), never bbf_bench.CHAIN_PINNED;
        # BB.noise fills chain_src_nv_rthz / delta_f_at_5mhz from bbf_bench.chain_ref(): both are overwritten here
        CREF = chain_reference()
        for r in nz:
            k = 'ss' if r['corner'].get('mos') == 'ss' else 'tt'
            nf0, gch, inv = CREF['nf_dsb_db'][k], CREF['gain_db_by'][k], r.get('in_nv_rthz_5mhz')
            if nf0 is None or gch is None or inv is None:
                r.update(chain_src_nv_rthz=None, delta_f_at_5mhz=None, chain_nf_dsb_db_no_filter=None, chain_nf_dsb_db_with_filter=None)
                continue
            src = BB.chain_source_noise_v(gch)
            r['chain_src_nv_rthz'] = src * 1e9
            r['delta_f_at_5mhz'] = (inv * 1e-9 / src) ** 2
            r['chain_nf_dsb_db_no_filter'] = round(nf0, 3)
            r['chain_nf_dsb_db_with_filter'] = 10 * math.log10(10 ** (nf0 / 10) + r['delta_f_at_5mhz'])
        pen = lambda r: r['chain_nf_dsb_db_with_filter'] - r['chain_nf_dsb_db_no_filter']
        have = [r for r in nz if r.get('chain_nf_dsb_db_with_filter') is not None]
        agc = min((g for g in sorted(set(r['pga_db'] for r in have))
                   if all(pen(q) <= 0.3 for q in have if q['pga_db'] == g)
                   and len([q for q in have if q['pga_db'] == g]) == 2), default=None) if CREF['available'] else None
        perf.append({'id': 'RF-RX-NF', 'metric': 'filter noise (PGA code, reset cap/Q codes): input-referred density at 1 / 5 MHz, output rms '
                     '0.1-10 MHz, and the chain NF with the filter (F_chain + (v_in,filter / v_src at the filter input)^2; LNA + mixer '
                     'gain and chain NF without the filter: the lna_close.py chain points of the cells on disk, tt and ss 32 C 3.15 V, '
                     'see chain_reference; AGC row = lowest PGA code meeting <= 0.3 dB at BOTH tt and ss)',
                     'target': 'AGC requirement: the PGA code at sensitivity keeps the filter penalty <= 0.3 dB',
                     'agc_min_pga_db_for_0p3db': agc, 'chain_reference': CREF,
                     'pass': (agc is not None and agc <= 21) if CREF['available'] else NA, 'rows': nz,
                     'note': ('at PGA 0 dB the filter adds several dB, so the AGC holds the PGA at or above agc_min_pga_db_for_0p3db until '
                              'the input is well above sensitivity') if CREF['available'] else
                             f"chain penalty {NA}: no chain point of the cells on disk ({CREF['source']}); filter-alone noise rows are valid"})
        perf.append({'metric': 'corner sweep (ext, RX reset cap code 8 (bw0), gain 0, reset Q code)', 'rows': corner_table(
            lambda c: tb.bbf_ac(w, 'ext', c, block, tag='rx'), ['f3db_hz', 'dc_gain_db', 'peak_gain_db', 'idd_a', 'out_cm_v'], BBF_CORNERS)})
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
    rec['excluded_coverage'] = ['fully differential 5th-order Butterworth (stage-1 real pole + 2 Tow-Thomas biquads), FD two-stage OTAs with '
                                'continuous CMFB to atb_vcm (fork S, bbf_fd.py); cutoff: cap code 0..127 (bw0..3 coarse x 8 + fc_fine0..2), '
                                'Q: 4-bit qt (Q = q_top (1 - 0.032 k), reset 6), both set per part at bring-up (trim rows above are the per-corner codes)',
                                'PGA -6..42 dB: stage-1 conductance k/4 (6 bits) x two +12 dB biquad steps (gainc0/1); netlists.GAIN_TABLE',
                                'narrowest corner limited by the capacitor bank (~1.2 MHz): LoRa 203/406 kHz needs a lower cutoff: open',
                                'noise: rows above (filter alone + chain-NF penalty); linearity only via the TX-observe HD3 points',
                                'validator rule (FS-1): cap code <= 1 requires qt >= 6 (stability margin at the highest integrator frequency)',
                                'no Monte Carlo (CMFB and DCOC range cover mismatch offsets by design, not verified statistically)',
                                'trim search is per corner on the extracted netlist; a production calibration routine (inject + observe) is not modelled']
    return finish(rec, perf, BBF_CORNERS, 'bbfilter 12-point tt/ss/ff')


# ---------------------------------------------------------------- bb_tap
TAP_F3DB_MIN_HZ = 20e6


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
            {'metric': 'observe -3 dB bandwidth into 10 pF (Hz)', 'target': '>= 20e6', 'extracted_nominal': obs.get('f3db_hz'),
             'pass': obs.get('f3db_hz') is not None and obs['f3db_hz'] >= TAP_F3DB_MIN_HZ},
            {'metric': 'gain at 20 MHz (dB), AC / transient 0.4 Vpp diff', 'extracted_nominal': [obs.get('gain_20mhz_db'), obs.get('tran_gain_20mhz_db')]},
            {'metric': 'pad common mode in observe (V)', 'extracted_nominal': obs.get('pad_cm_v'),
             'note': 'NMOS follower level shift; external ADC must accept ~0.8 V CM'},
            {'metric': 'inject pad -> chain node gain (dB)', 'extracted_nominal': inj.get('pad_to_node_gain_db')},
            {'metric': 'supply current observing (mA)', 'extracted_nominal': obs['idd_a'] * 1e3 if obs.get('idd_a') else None}]
    if not quick:
        sweep = corner_table(lambda c: tb.tap_observe(w, 'ext', c), ['lf_gain_db', 'f3db_hz', 'gain_20mhz_db', 'pad_cm_v', 'idd_a'])
        ok, bad = corner_pass(sweep, {'f3db_ge_20mhz': lambda r: r['f3db_hz'] >= TAP_F3DB_MIN_HZ,
                                      'lf_gain_gt_m6_db': lambda r: r['lf_gain_db'] > -6})
        perf.append({'metric': 'corner sweep (ext observe): low-frequency gain, -3 dB bandwidth into 10 pF, gain at 20 MHz, pad CM, supply current',
                     'target': 'every corner: -3 dB bandwidth >= 20 MHz; gain > -6 dB (the basic-function threshold of the clean test)',
                     'corners': corner_note(), 'pass': ok, 'failing_rows_by_check': bad, 'rows': sweep})
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
    rec['excluded_coverage'] = ['pad protection network not co-simulated (pad modelled as ideal node + 10 pF)',
                                'extraction is capacitance-only (no wire / via resistance)',
                                'linearity/THD, noise not quantified', 'no Monte Carlo']
    return finish(rec, perf)


# ---------------------------------------------------------------- RF chain (current cells)
CHAIN_VIEW = 'extpr'      # extracted + pad_rf_pair delta + Rg 150 ohm / 10 um (the nominal model end, as lna_close.chain_point)
CHAIN_D_MM = 2.0          # carrier parts at connector + 2 mm


def channel_match(w, view=CHAIN_VIEW, c=NOM, d_mm=CHAIN_D_MM):
    """Per-chip carrier match on the real COB channel for the LNA now on disk (same calls as lna_close.chain_point)."""
    import lna_close
    import lna_match as LM
    ct = lna_close.TANK_CT.get((view, c[0]), 9)
    u = tb.lna_ac(w, view, c, f=2.44e9, ct=ct)
    m, s11, loss = LM.channel_fit(complex(u['zin_re_ohm'], u['zin_im_ohm']), d_mm=d_mm)
    m['ct'] = ct
    return m, dict(tank_ct=ct, pad_zin_ohm=[u['zin_re_ohm'], u['zin_im_ohm']], carrier_parts=m['parts'], carrier_distance_mm=d_mm,
                   fit_s11_worst_db=s11, fit_in_band_loss_db=loss)


def match_net_without_collision(m):
    """tb._ladder_net names the node between the bond wire and the rest of the ladder bqp / bqn; tb.chain_tran (and
    tb.chain_det) use bqp / bqn for the Q mixer's baseband output.  With a ladder match the Q TIA output and its 1 pF load are
    therefore tied to the RF path behind the bond (first run here: Q gain -6.3 dB, I 31.8 dB, IRR 0.2 dB).  tb.py is not
    edited from here; the deck fragment is renamed instead."""
    import re
    return re.sub(r'\bbq([pn])(a?)\b', r'bwj\1\2', _TB_MATCH_NET(m))


_TB_MATCH_NET = tb._match_net
MATCH_FIX = 'ladder nodes bqp/bqn (tb._ladder_net) renamed: they collided with the Q baseband output nodes of tb.chain_tran'


def run_chain(quick, resume=False, lo_stretch=False):
    """generated/rf_rx_chain.json: conversion gain and I/Q balance of the extracted LNA + both extracted mixers (tb.chain_tran,
    ideal square LO) and the chain-NF points of lna_close.py when they belong to the cells on disk.  Bound to the three
    extracted netlists by sha256 (load_chain refuses the file when they differ)."""
    w = WORK / 'chain'
    hashes = cell_hashes()
    old = json.loads((GEN / 'rf_rx_chain.json').read_text()) if resume and (GEN / 'rf_rx_chain.json').exists() else {}
    if old.get('netlist_sha256') != hashes:
        old = {}
    try:
        m, minfo = channel_match(w / 'match')
    except Exception as e:          # no match -> no matched point; recorded, never replaced by an older network
        m, minfo = None, {'error': repr(e)[-600:]}
    def need_match(fn):
        def job():
            if m is None:
                raise RuntimeError(f"no channel match for the LNA on disk: {minfo['error']}")
            return fn()
        return job
    def matched():
        tb._match_net = match_net_without_collision
        try:
            return dict(tb.chain_tran(w, CHAIN_VIEW, match=m), bench_fix=MATCH_FIX)
        finally:
            tb._match_net = _TB_MATCH_NET
    jobs = {'ext_m': need_match(matched)}
    if not quick:
        jobs['ext_u'] = lambda: tb.chain_tran(w, CHAIN_VIEW)
        jobs['ext_byp'] = lambda: tb.chain_tran(w, CHAIN_VIEW, mode='bypass')
    if lo_stretch:
        for f in (1.2e9, 0.6e9):
            def lo_job(f=f):
                a = tb.lna_ac(w, CHAIN_VIEW, NOM, 'active', f=f)
                mm = tb.board_match(complex(a['zin_re_ohm'], a['zin_im_ohm']), f=f)
                return tb.chain_tran(w, CHAIN_VIEW, flo=f, fif=2e6, match=mm)
            jobs[f'ext_ideal_lmatch_{int(f / 1e6)}MHz'] = lo_job
    keep = {k: v for k, v in old.items() if k in jobs and isinstance(v, dict) and 'error' not in v
            and (k != 'ext_m' or v.get('bench_fix') == MATCH_FIX)}
    todo = [k for k in jobs if k not in keep]
    res = dict(keep, **dict(zip(todo, par([jobs[k] for k in todo]))))
    nfr, src = chain_nf_rows()
    out = {'netlist_sha256': hashes,
           'conditions': {'view': CHAIN_VIEW, 'corner': 'tt 27 C 3.3 V', 'lo': 'ideal 0/VDD square, 50 % duty, 20 ps edges (tb.chain_tran has no real-LO option)',
                          'source': '100 ohm differential EMF; ext_m: real COB channel ladder + per-chip carrier parts (lna_match.channel_fit, lossy, '
                                    'pessimistic part Q); ext_u / ext_byp: source directly on the pads',
                          'points_run': list(jobs), 'quick': quick},
           'channel_match': minfo}
    out.update({k: res[k] for k in jobs})
    out['chain_nf'] = ({'state': NA, 'reason': src} if nfr is None else
                       {'state': 'pass' if all(r.get('nf_dsb_db') is not None and r['nf_dsb_db'] <= CHAIN_NF_DSB_DB_MAX for r in nfr) else 'fail',
                        'target_dsb_db': CHAIN_NF_DSB_DB_MAX, 'source': src, 'rows': nfr})
    (GEN / 'rf_rx_chain.json').write_text(json.dumps(out, indent=1, default=str) + '\n')
    return out


def refresh_chain_rows(block):
    p = GEN / f'{block}-evidence.json'
    rec = json.loads(p.read_text())
    if (rec.get('simulated_netlist_sha256') or {}).get(f'{block}.ext.spice') != flow.sha256(GEN / f'{block}.ext.spice'):
        print(block, 'evidence does not belong to the extracted netlist on disk: not refreshed (rerun the block)')
        return
    perf = rec['performance_vs_target']
    is_chain = lambda r: r['metric'].startswith('chain ')
    at = next((i for i, r in enumerate(perf) if is_chain(r)), len(perf))
    keep = [r for r in perf if not is_chain(r)]
    n_before = sum(not is_chain(r) for r in perf[:at])
    perf = keep[:n_before] + chain_rows_for_mixer() + keep[n_before:]
    corners = [(c['mos'], c['temp_c'], c['vdd_v']) for c in rec['corner_set']['corners']]
    rec = finish(rec, perf, corners, rec['corner_set']['name'])
    rec['chain_rows_refreshed'] = 'chain-derived rows rewritten by characterize.py --refresh-chain-rows (no mixer re-simulation)'
    p.write_text(json.dumps(rec, indent=1, default=str) + '\n')
    print(block, 'performance:', rec['performance_state'], 'failing:', rec['failing_rows'], 'not available:', [x[:40] for x in rec['rows_not_available']])


def main():
    global POOL, CORNERS, CORNER_SET
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--corners', choices=sorted(CORNER_SETS), default='full', help='rxmix / bb_tap corner set (recorded in the evidence)')
    ap.add_argument('--resume-chain', action='store_true',
                    help='reuse error-free chain points of generated/rf_rx_chain.json if it belongs to the netlists on disk')
    ap.add_argument('--chain-lo-stretch', action='store_true', help='also run the 1.2 / 0.6 GHz LO points (ideal lossless L-match)')
    ap.add_argument('--refresh-chain-rows', action='store_true',
                    help='no simulation: rewrite only the chain-derived rows (IRR, chain NF, IIP3) of the rxmix evidence from '
                         'generated/rf_rx_chain.json / the lna_close chain points, if the evidence belongs to the mixer netlist on disk')
    ap.add_argument('--blocks', nargs='*', default=['chain', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'bb_tap'])
    a = ap.parse_args()
    known = ('chain', 'lna') + tuple(b for b in flow.BLOCKS if b != 'lna')
    bad = [b for b in a.blocks if b not in known]
    if bad:
        ap.error(f'unknown block(s) {bad}; known: {known}')
    CORNER_SET, CORNERS = a.corners, CORNER_SETS[a.corners]
    if a.refresh_chain_rows:
        for b in ('rxmix_i', 'rxmix_q'):
            refresh_chain_rows(b)
        return
    POOL = ThreadPoolExecutor(a.jobs)
    if 'chain' in a.blocks:
        c = run_chain(a.quick, a.resume_chain, a.chain_lo_stretch)
        print('chain', {k: ({x: v.get(x) for x in ('gain_i_db', 'gain_q_db', 'irr_db', 'error') if x in v}) for k, v in c.items()
                        if k.startswith('ext_')}, 'chain_nf:', c['chain_nf']['state'])
    for b in a.blocks:
        if b == 'chain':
            continue
        if b == 'lna':
            print(LNA_MSG)
            continue
        if b.startswith('rxmix'):
            rec = do_rxmix(b, a.quick)
        elif b.startswith('bbfilter'):
            rec = do_bbf(b, a.quick)
        else:
            rec = do_tap(a.quick)
        (GEN / f'{b}-evidence.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
        print(b, {k: v['state'] for k, v in rec['tests'].items()}, 'performance:', rec['performance_state'],
              'failing:', rec['failing_rows'], 'not available:', rec['rows_not_available'])


if __name__ == '__main__':
    main()
