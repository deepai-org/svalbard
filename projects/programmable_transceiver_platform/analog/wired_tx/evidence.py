"""Assemble generated/*-evidence.json (spec/block-deliverables.md schema) from the
stored layout and simulation results.  Nothing here is assumed: every state is
derived from the recorded numbers, and missing runs leave the test 'open'."""
import json
from pathlib import Path
import tools

W = tools.SCRATCH
GEN = tools.GENERATED
REL = lambda p: str(Path(p).resolve().relative_to(tools.PROJECT))


def _load(name):
    p = W / name
    return json.loads(p.read_text()) if p.exists() else {}


def _pex_cap_ff(net):
    tot = 0.0
    scale = {'f': 1, 'p': 1e3, 'a': 1e-3}
    for line in (GEN / 'wiredtx.ext.spice').read_text().splitlines():
        if line.startswith('C'):
            p = line.split()
            if net in p[1:3]:
                v = p[3]
                tot += float(v[:-1]) * scale[v[-1]] if v[-1] in scale else float(v) * 1e15
    return round(tot, 2)


def _serial_ok(r):
    m = (r or {}).get('CMD_MAIN_N', {})
    return bool(r and r.get('ok') and m.get('errors') == 0)


def _summary(r):
    if not r:
        return None
    m = r.get('CMD_MAIN_N', {})
    return dict(bit_rate_bps=r.get('bit_rate_bps'), bits_per_ring_cycle=r.get('bits_per_ring_cycle'),
                ring_hz=r.get('ring_hz'), corner=r.get('corner'), temp_c=r.get('temp_c'), vdd=r.get('vdd'),
                bits_compared=m.get('bits_compared'), errors=m.get('errors'),
                cmd_jitter_pp_ps=round(m['jitter_pp_s'] * 1e12, 1) if 'jitter_pp_s' in m else None,
                cmd_eye_width_ps=round(m['eye_width_est_s'] * 1e12, 1) if 'eye_width_est_s' in m else None,
                postcursor_mismatches_vs_main_delayed_1ui=(r.get('CMD_POST_P') or {}).get(
                    'mismatches_vs_main_delayed_1ui'),
                word_clk_period_ns=round(r['word_clk_period_s'] * 1e9, 3) if r.get('word_clk_period_s') else None,
                supply_current_avg_ma=round(r['supply_current_avg_a'] * 1e3, 2) if r.get('supply_current_avg_a') else None,
                tail_current_ma={k: (round(v * 1e3, 3) if v is not None else None) for k, v in (r.get('tail_current_a') or {}).items()},
                tj_1e12_ui=_tj_ui(r),
                pass_=_serial_ok(r), reason=r.get('reason') or r.get('error'))


RJ_RMS_S = 2e-12   # ring random jitter budget (spec/interface-architecture-changes.md S5: <= 2 ps rms)
Q_1E12 = 7.034


def _tj_ui(r):
    """Total jitter at BER 1e-12 at the pre-driver output, in UI: the simulated deterministic
    jitter (peak-peak crossing spread over >= 2 PRBS7 periods, ideal ring phases) plus the
    ring RJ budget, TJ = DJ_pp + 2 Q(1e-12) RJ_rms.  The serializer itself adds no RJ in
    simulation; pad, package and channel are not included."""
    m = (r or {}).get('CMD_MAIN_N', {})
    if 'jitter_pp_s' not in m or not r.get('bit_rate_bps'):
        return None
    return round((m['jitter_pp_s'] + 2 * Q_1E12 * RJ_RMS_S) * r['bit_rate_bps'], 3)


def _eye(r):
    if not r:
        return None
    e = r.get('eye', {})
    return dict(mode=r.get('mode'), bit_rate_bps=r.get('bit_rate_bps') or r.get('rate_bps'),
                bits_per_ring_cycle=r.get('bits_per_ring_cycle'), network=r.get('network'),
                lossy_channel=r.get('lossy_channel'), receiver=r.get('receiver'),
                eye_height_mv=round(e['eye_height_v'] * 1e3, 1) if 'eye_height_v' in e else None,
                eye_width_ps=round(e['eye_width_est_s'] * 1e12, 1) if 'eye_width_est_s' in e else None,
                amplitude_pp_mv=round(e['amplitude_pp_v'] * 1e3, 1) if 'amplitude_pp_v' in e else None,
                bits=e.get('n_bits'), errors=e.get('errors'), pad_levels_v=r.get('pad_levels_v'),
                vdd_current_ma=round(r['vdd_current_avg_a'] * 1e3, 2) if r.get('vdd_current_avg_a') else None,
                pass_=bool(r.get('ok')), reason=r.get('reason') or e.get('reason') or r.get('error'))


def common_header():
    srcs = ['cells.py', 'layoutgen.py', 'tools.py', 'sim_wiredtx.py', 'sim_integration.py', 'sim_static.py',
            'run_all.py', 'evidence.py', 'wiredtx.spice', 'wtx_ext_rx.spice']
    return dict(source_hashes={s: tools.sha(tools.HERE / s) for s in srcs},
                images=dict(analog=tools.image_id(tools.ANALOG_IMAGE), digital=tools.image_id(tools.DIGITAL_IMAGE),
                            digital_tag=tools.DIGITAL_IMAGE,
                            pad_integration_simulator=dict(path=str(tools.PAD_NGSPICE.relative_to(tools.REPO)),
                                                           sha256=tools.sha(tools.PAD_NGSPICE),
                                                           note='pads-recorded patched ngspice-47 '
                                                                '(analog/pads/generated/simulator-build.json)')),
                pdk='gf180mcuD (open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7; identical model/tech/'
                    'netgen files in both images)')


def build():
    lay = _load('layout-result.json')
    raw = _load('sim-results.json')
    # Only results simulated on the current netlists count.  Every result carries
    # the sha256 of the netlist it read (dut_sha256); anything else (older layout,
    # no hash recorded) is dropped from the tests, the performance list and the
    # README table and only listed by name under stale_results_excluded.
    cur_sha = dict(extracted=tools.sha(GEN / 'wiredtx.ext.spice'), schematic=tools.sha(tools.HERE / 'wiredtx.spice'))
    sims, stale = {}, []
    for k, v in raw.items():
        if not isinstance(v, dict):
            continue
        kind = v.get('dut_kind') or ('schematic' if k.startswith('schematic') else 'extracted')
        if v.get('dut_sha256') and v.get('dut_sha256') == cur_sha[kind]:
            sims[k] = v
        else:
            stale.append(dict(run=k, dut_sha256=v.get('dut_sha256'), kind=kind))
    lr = lay.get('layout', {})
    drc0 = lr.get('drc_count') == 0
    kl0 = (lay.get('klayout') or {}).get('violations') == 0
    lvs = bool((lay.get('lvs') or {}).get('unique_match'))
    # clean gate: 0.96 Gb/s half rate (lowest ring frequency, 480 MHz) - the highest
    # simulated point that passes all twelve required corners; 1.25 Gb/s is recorded
    nominal = sims.get('nominal')
    corners = {}
    env = [(c, tt, v) for c in ('typical', 'ss', 'ff', 'sf', 'fs') for tt in (22, 32) for v in (3.15, 3.35)]
    need = {f'corner096_{c}_{tt}_{v}' for c, tt, v in env}
    missing_corners = sorted(need - set(corners))
    corners_pass = not missing_corners and all(c and c['pass_'] for c in corners.values())
    # quarter rate (compact core): 2.5 Gb/s gates clean; 3.24 Gb/s (ring 810 MHz) is recorded
    qsets = {}
    for q, pre, pts in (('quarter 2.5', 'cornerq2.5_', env), ('half 1.62', 'cornerh1.62_', env),
                        ('full 0.48', 'cornerf0.48_', env)):
        got = {k: _summary(v) for k, v in sims.items() if k.startswith(pre)}
        miss = sorted({f'{pre}{c}_{tt}_{v}' for c, tt, v in pts} - set(got))
        qsets[q] = dict(runs=got, missing=miss, all_pass=not miss and all(s and s['pass_'] for s in got.values()),
                        points=len(pts))
    # clean gate (path A, session 6): PCIe-rate quarter rate (2.5), the top half rate (1.62 = ring 810 MHz,
    # core at 3.24 Gb/s internally; covers TMDS / SDI 1.485, SATA 1.5, SGMII 1.25) and full rate at the
    # slowest ring (0.48 = USB HS, ring 480 MHz) on all 20 envelope points
    gating = ('quarter 2.5', 'half 1.62', 'full 0.48')
    clean_pass = drc0 and kl0 and lvs and _serial_ok(nominal) and all(qsets[g]['all_pass'] for g in gating)
    off = [sims.get(k) for k in ('unpowered_tt', 'unpowered_ff_85_3v63')]
    qs = [sims.get(k) for k in ('quiescent_stopped_tt', 'quiescent_stopped_ff_85_3v63')]
    qr = [sims.get(k) for k in ('quiescent_tt', 'quiescent_ff_85_3v63')]
    ramps = [sims.get(k) for k in ('ramp_tt', 'ramp_ff_85_3v63')]

    def off_ok(r):
        return bool(r and 'i_rail_backfeed_a' in r and abs(r['i_rail_backfeed_a']) < 1e-6 and
                    max(abs(r[k]) for k in ('i_ser_en_a', 'i_d0_a', 'i_ph0_a', 'i_island_off_a')) < 1e-6 and
                    max(r[k] for k in ('v_cmd_main_n', 'v_cmd_main_p', 'v_cmd_tmds_p', 'v_main_bias')) < 0.1)

    def q_ok(r):
        return bool(r and max(r.get(k, 9) for k in ('cmdmax', 'cmdmax2', 'pmax')) < 0.3 and
                    max(r.get(k, 9) for k in ('biasmax', 'tbiasmax')) < 0.3)
    safe_pass = all(off_ok(r) for r in off) and all(q_ok(r) for r in qs + qr) and \
        all(r and r.get('max_cmd_v', 9) < 0.5 for r in ramps)
    dac = sims.get('dac_tt', {})
    ext1 = sims.get('ext_ideal_1g')
    exr = {k: sims.get(k) for k in ('ext_rx_0g5', 'ext_rx_1g', 'ext_rx_1g6', 'ext_rx_2g')}
    ho = sims.get('ext_handover')
    fallback_pass = bool(ext1 and ext1.get('ok') and ho and ho.get('ok'))
    head = common_header()
    head['netlist_hashes'] = dict(extracted=cur_sha['extracted'], schematic=cur_sha['schematic'],
                                  lvs_layout=tools.sha(GEN / 'wiredtx.lvs.spice'), gds=tools.sha(GEN / 'wiredtx.gds'))
    head['stale_results_excluded'] = stale
    perf = []
    for k, v in sims.items():
        if k.startswith('sweep_') or k in ('schematic_q2g5', 'nominal'):
            s = _summary(v)
            s['run'] = k + (' (schematic, no parasitics)' if k.startswith('schematic') else ' (extracted)')
            perf.append(dict(metric='serializer data at pre-driver outputs vs bit rate / mode', **s))
    for k in sorted(x for x in sims if x.startswith('int_') and x != 'int_mlt3_125mbd_b39'):
        if sims.get(k):
            perf.append(dict(metric='pad eye (pt_wiredtx extracted + pads steering buffers + extracted pad)',
                             run=k, **_eye(sims[k])))
    for q, s in qsets.items():
        for k, v in s['runs'].items():
            perf.append(dict(metric=f'{q} Gb/s (compact core) across the envelope', run=k, **v))
    if sims.get('int_mlt3_125mbd_b39'):
        m = sims['int_mlt3_125mbd_b39']
        perf.append(dict(metric='IX-9 MLT-3 125 MBd (MAIN + POST, POST_POL = 1) through board network B39',
                         run='int_mlt3_125mbd_b39', **{k: m.get(k) for k in (
                             'bit_rate_bps', 'symbol_rate_bd', 'codes', 'network', 'symbols', 'levels_v', 'peak_v',
                             'zero_residue_v', 'zero_residue_pct_of_peak', 'pad_levels_v', 'vdd_current_avg_a', 'ok',
                             'reason')}))
    for k, v in sims.items():
        if k.startswith('corner_'):
            perf.append(dict(metric='1.25 Gb/s half-rate across the corner set (stretch over nominal)', run=k,
                             **_summary(v)))
    if dac.get('rows'):
        perf.append(dict(metric='tail-bias DAC transfer (replica of the pad tail, drain 1.0 V)',
                         target='wiredtx 2-16 mA (8 mA nominal); TMDS ~10 mA',
                         rows=[{k: (round(v * 1e3, 3) if k.startswith('i_') else v) for k, v in r.items()}
                               for r in dac['rows']], units='mA for i_*'))
    ev = dict(block='wiredtx', **head, tests=dict(
        safe=dict(state='pass' if safe_pass else ('open' if not all(off + qs + ramps) else 'fail'),
                  cases=[x for x in off + qs + qr + ramps if x],
                  notes='Unpowered island with every core-domain input, phase and code high: no rail back-feed, '
                        'inputs draw no current (word inputs are buffered, all control inputs are MOS gates), '
                        'outputs clamped by ISLAND_OFF. Reset defaults (SER_EN=0, WTX_EXT=0, EN_*=0): every '
                        'command output and tail bias held low; the only static current is the bias mirror '
                        'when an enable is set. Safety corners ff/85 C/3.63 V included. Mutual exclusion of '
                        'MAIN/TMDS/POST is the pads interlock (EN_* inputs); this block gates each branch with '
                        'its enable and selects serializer vs external data break-before-make.'),
        clean=dict(state='pass' if clean_pass else 'fail',
                   drc=dict(magic=dict(errors=lr.get('drc_count'), style='drc(full), flattened',
                                       tool='Magic (digital image)', report=REL(GEN / 'wiredtx-drc.txt')),
                            klayout=lay.get('klayout'), gds_export=lay.get('gds_export')),
                   lvs=dict(unique_match=lvs, summary=(lay.get('lvs') or {}).get('summary'),
                            report=REL(GEN / 'wiredtx-lvs.txt')),
                   extracted_nominal=dict(point='tt, 27 C, 3.3 V, 1.25 Gb/s half rate (MODE 10 = WT12 rep2, ring '
                                                '625 MHz, core 2.5 Gb/s), PRBS7, extracted C (Magic)',
                                          **(_summary(nominal) or {})),
                   corner_sets={f'{q} Gb/s': dict(points=s['points'], all_pass=s['all_pass'], missing=s['missing'],
                                                  gating=q in gating,
                                                  failing=sorted(k for k, v in s['runs'].items() if not v['pass_']))
                                for q, s in qsets.items()},
                   envelope='tt/ss/ff/sf/fs x 22/32 C x 3.15/3.35 V (20 points) for every gating set',
                   area_um2=lr.get('area_um2'), area_allocation_um2=300000, devices=lr.get('devices')),
        observable=dict(state='pass' if dac.get('rows') and ext1 else 'open',
                        atb_taps=['ATB_NBIAS (bias reference diode)', 'ATB_PBIAS (MAIN DAC PMOS mirror gate)',
                                  'MAIN_BIAS / POST_BIAS / TMDS_BIAS (tail gate voltages, sense through atb_tap; '
                                  'register-map ATB node 26 wiredtx_bias)'],
                        atb_evidence='dac_tt rows: ATB voltages vs code',
                        status_bits=['WTX_EXT_DATA -> wire_status wtx_ext_data (buffered DX)'],
                        clock_obs=['WORD_CLK (bit rate / 20) -> WCLK_OBS divider/mux input'],
                        notes='Serial data is also observable at the pad through the PRBS patterns of '
                              'rtl/pt_pattern.sv and the RX checker (loopback).'),
        fallback=dict(state='pass' if fallback_pass else 'open',
                      routes=['wire_tx_external_data (debug.wtx_ext): WTX_EXT_P/N -> pt_diff_clk_rx (timing) -> DX '
                              '-> break-before-make select in pt_wtx_predrv -> MAIN/TMDS steering commands',
                              'reduced-rate modes of the same core (MODE 10 / 01 = WT12 2x / 4x repetition): every '
                              'line rate down to 0.48 Gb/s with the core at <= 3.24 Gb/s internally',
                              'session 6: the generic static-CMOS serializer (MODE 11) was removed (interface WT13); '
                              'MODE 11 now runs half rate on the core'],
                      bypass_loading_fF=dict(DX_routing=_pex_cap_ff('DX'),
                                             DX_gates='INV1 (1/2 um) + NAND (4/4 um) gates, ~15 fF estimate'),
                      evidence=dict(ideal_dx_1g=_eye(ext1), shared_receiver={k: _eye(v) for k, v in exr.items()},
                                    break_before_make=ho))),
        performance_vs_target=perf,
        excluded_coverage=[
            'Pad-integration runs use the pads family extracted netlists read-only and their recorded patched '
            'ngspice-47; termination common mode is an ideal 1.65 V source (pads termination buffer not '
            'included); bond 1 ohm / 1 nH per leg; no package model beyond that.',
            'Extraction is capacitance only (no distributed resistance).',
            'The 20-bit word source is ideal PWL launched T_word/4 after WORD_CLK; the standard-cell pattern '
            'RTL (rtl/pt_pattern.sv) is not co-simulated.',
            'Ring phases are ideal 50 % duty, exactly 90 deg apart, tanh edges (10-90 % 50 ps) through 150 ohm; '
            'ring jitter (except the 2 ps rms RJ budget added to TJ), phase-spacing error and the clockmux are '
            'not included.  The core needs <= ~10 ps phase-to-phase skew (interface WT2).',
            'Stimuli are breakpoint-free behavioural sources (tanh edges) behind 150 ohm (phases) / 1 kohm '
            '(word bits, controls) driver resistances.  Ideal PWL/PULSE sources made ngspice abort at '
            'source corners (C/h-dominated branch currents could not converge to abstol); no simulator '
            'tolerance was changed.',
            'The serializer bench loads each tail-bias node with its pad tail device (drain tied to source); '
            'tail currents are measured by the DC benches (dac_tt, quiescent), not in the transient runs.',
            'Envelope runs use 200 bits (>1.5 PRBS7 periods), nominal/integration 280 bits: error-free '
            'windows, not a measured BER; TJ(1e-12) = simulated DJ_pp + 14.07 x 2 ps rms ring RJ budget.',
            'Rate sweep at tt only; envelope sets as listed under clean.corner_sets.',
            'No Monte Carlo, aging, EM/IR or antenna analysis; density fill is left to top-level assembly.'])
    tools.write_json(GEN / 'wiredtx-evidence.json', ev)
    # TMDS configuration record
    tm = sims.get('int_tmds_h1g25')
    tm_e = _eye(tm)
    ev_t = dict(block='tmds', **head, configuration_of='wiredtx (spec/consolidation-pass.md item 4)', tests=dict(
        safe=dict(state=ev['tests']['safe']['state'], cases=['see wiredtx-evidence.json safe'],
                  notes='Same hardware as wiredtx; EN_TMDS gates the TMDS steering commands and the TMDS tail DAC.'),
        clean=dict(state='pass' if (clean_pass and tm and tm.get('ok')) else 'fail',
                   drc=ev['tests']['clean']['drc'], lvs=ev['tests']['clean']['lvs'],
                   extracted_nominal=dict(point='tt, 27 C, 3.3 V, 1.25 Gb/s half-rate mode; pt_wiredtx extracted '
                                                '-> pads steering buffers -> extracted pad TMDS branch; on-chip '
                                                'termination off; 50 ohm per leg to an independent 3.3 V',
                                          **(tm_e or {}))),
        observable=dict(state=ev['tests']['observable']['state'], atb_taps=['TMDS_BIAS'], status_bits=[],
                        clock_obs=['WORD_CLK']),
        fallback=dict(state=ev['tests']['fallback']['state'], routes=['wire_tx_external_data (TMDS branch)'],
                      bypass_loading_fF=None)),
        performance_vs_target=[x for x in [_eye(sims.get('int_tmds_q2g97'))] if x],
        excluded_coverage=['TMDS code 125 (~10 mA tail) used; no HDMI compliance (rise time, skew, eye mask) '
                           'evaluation; no 10-bit TMDS encoding (digital).'])
    tools.write_json(GEN / 'tmds-evidence.json', ev_t)
    # external-data receiver instance
    tim = tools.PROJECT / 'analog/timing/generated/diff_clk_rx-evidence.json'
    tim_ev = json.loads(tim.read_text()) if tim.exists() else {}
    ev_x = dict(block='wtx_ext_rx', **head, instance_of='pt_diff_clk_rx (analog/timing, consolidation item 6)',
                tests=dict(
        safe=dict(state=(tim_ev.get('tests', {}).get('safe', {}) or {}).get('state', 'open'),
                  cases=['owned by analog/timing diff_clk_rx-evidence.json'], notes='EN=debug.wtx_ext.enable; SE=0.'),
        clean=dict(state=(tim_ev.get('tests', {}).get('clean', {}) or {}).get('state', 'open'),
                   reference='analog/timing/generated/diff_clk_rx-evidence.json',
                   path_simulation={k: _eye(v) for k, v in exr.items()}),
        observable=dict(state='pass' if ext1 else 'open', status_bits=['WTX_EXT_DATA', 'PRESENT'],
                        atb_taps=['ATB_DET']),
        fallback=dict(state='n/a', routes=[], notes='This receiver is itself the fallback route for wiredtx.')),
        performance_vs_target=[{k: _eye(v)} for k, v in exr.items()],
        excluded_coverage=['Receiver design, layout and DRC/LVS belong to analog/timing.'])
    tools.write_json(GEN / 'wtx_ext_rx-evidence.json', ev_x)
    hs_l, hs_s = _load('hs-layout-result.json'), _load('hs-sim-results.json')
    if hs_l:
        hl = hs_l['layout']
        sw = {k: v for k, v in hs_s.items() if k != 'settle'}
        ok_c = all(v.get('monotonic') and 0.4 < (v.get('full_scale_v') or 0) < 0.8 and
                   abs((v.get('disabled') or {}).get('v_hs_pbias', 0) - v['vdd']) < 0.01 for v in sw.values())
        hs_clean = hl['drc_count'] == 0 and hs_l['klayout'].get('violations') == 0 and hs_l['lvs']['unique_match'] \
            and bool(hs_s.get('tt', {}).get('monotonic'))
        ev_h = dict(block='usb_hs_bias (pt_wtx_hsbias, P3-12)', **head, tests=dict(
            safe=dict(state='pass' if all((v.get('disabled') or {}).get('i_vdd_a', 1) < 1e-6 for v in sw.values()) else 'fail',
                      cases=[dict(corner=k, disabled=v.get('disabled')) for k, v in sw.items()],
                      notes='EN=0 (reset/HS disabled): sources off, load released, HS_PBIAS pulled to island VDD '
                            '(wirepad HS mirror off), no static current. Island off: all devices unpowered, '
                            'inputs are MOS gates except IBIAS (NMOS drain).'),
            clean=dict(state='pass' if hs_clean else 'fail',
                       drc=dict(magic=hl['drc_count'], klayout=hs_l['klayout'], gds_export=hs_l['gds_export']),
                       lvs=hs_l['lvs'], area_um2=hl['area_um2'], devices=hl['devices'],
                       extracted_nominal=dict(point='tt 27 C 3.3 V, load 28 x pfet 20/1 + 0.3 pF', **hs_s.get('tt', {}))),
            observable=dict(state='open', atb_taps=['HS_PBIAS can be sensed through an atb_tap at integration'],
                            status_bits=[], clock_obs=[]),
            fallback=dict(state='n/a', routes=['USB HS through an external board PHY (tapeout-plan)'])),
            performance_vs_target=[dict(metric='full scale (target ~0.6 V), LSB (target <= 2.4 mV), monotonic, '
                                               'across tt/ss/ff x 22/32 C x 3.15/3.35 V', all_in_window=ok_c,
                                        corners={k: dict(full_scale_v=v.get('full_scale_v'), max_lsb_mv=v.get('max_lsb_mv'),
                                                         monotonic=v.get('monotonic')) for k, v in sw.items()}),
                                   dict(metric='settling 64->192 to 1 LSB (target 1 us)', **hs_s.get('settle', {}))],
            register_fields=dict(code='8 bits, HS_PBIAS ~ code x 2.3 mV (tt); suggested default 0 with EN=0',
                                 enable='1 bit (usb HS drive enable); 0 = HS_PBIAS at VDD'),
            excluded_coverage=['Load modelled as 28 ideal pfet gates + 0.3 pF, not the pads extracted wirepad.',
                               'Triode NMOS load: full scale varies with PVT (per-board calibration intended).'])
        tools.write_json(GEN / 'usb_hs_bias-evidence.json', ev_h)
    tools.write_json(GEN / 'wiredtx-sims.json', dict(layout=lay, sims=sims))
    readme_table(sims)
    return ev


def readme_table(sims):
    rows = ['<!-- RESULTS:BEGIN (generated by evidence.py) -->',
            '| Run | Rate | Bits/ring cycle | Corner | Result | Detail |', '| --- | --- | --- | --- | --- | --- |']
    for k, v in sims.items():
        tagk = k
        if 'CMD_MAIN_N' in v or k.startswith(('nominal', 'sweep', 'corner', 'schematic')) and 'eye' not in v:
            s = _summary(v)
            det = (f"{s['errors']} errors / {s['bits_compared']} bits, CMD jitter {s['cmd_jitter_pp_ps']} ps pp, "
                   f"post mism. {s['postcursor_mismatches_vs_main_delayed_1ui']}") if s['bits_compared'] else (s['reason'] or '')[:80]
            rows.append(f"| {tagk} | {(s['bit_rate_bps'] or 0)/1e9:g} Gb/s | {s['bits_per_ring_cycle']} | "
                        f"{s['corner']} {s['temp_c']} C {s['vdd']} V | {'pass' if s['pass_'] else 'FAIL'} | {det} |")
        elif 'eye' in v or k.startswith(('int_', 'ext_')) and k != 'ext_handover':
            e = _eye(v)
            det = (f"eye {e['eye_height_mv']} mV / {e['eye_width_ps']} ps, {e['amplitude_pp_mv']} mVpp diff, "
                   f"{e['errors']} errors / {e['bits']} bits") if e.get('bits') else (e.get('reason') or '')[:80]
            rows.append(f"| {tagk} | {(e['bit_rate_bps'] or 0)/1e9:g} Gb/s | {e.get('bits_per_ring_cycle') or '-'} | tt 27 C 3.3 V | "
                        f"{'pass' if e['pass_'] else 'FAIL'} | {det} |")
        elif k == 'ext_handover':
            rows.append(f"| {k} | - | - | tt 27 C 3.3 V | {'pass' if v.get('ok') else 'FAIL'} | SER off -> EXT on gap "
                        f"{round((v.get('break_before_make_gap_s') or 0)*1e9, 2)} ns, overlap samples {v.get('overlap_samples')} |")
        elif k.startswith('dac'):
            r = {x['code']: x for x in v.get('rows', [])}
            rows.append(f"| {k} | - | - | tt 27 C 3.3 V | data | MAIN code 109: {r.get(109, {}).get('i_tail_main_a', 0)*1e3:.2f} mA, "
                        f"TMDS 102/125: {r.get(102, {}).get('i_tail_tmds_a', 0)*1e3:.2f}/{r.get(125, {}).get('i_tail_tmds_a', 0)*1e3:.2f} mA, "
                        f"255: {r.get(255, {}).get('i_tail_main_a', 0)*1e3:.2f} mA |")
        elif k.startswith('unpowered'):
            rows.append(f"| {k} | - | - | {v.get('corner')} {v.get('temp_c')} C in {v.get('vin')} V | "
                        f"{'pass' if v.get('i_rail_backfeed_a') is not None and abs(v['i_rail_backfeed_a']) < 1e-6 else 'FAIL'} | "
                        f"rail back-feed {v.get('i_rail_backfeed_a')} A, max output {max(v.get(x, 0) for x in ('v_cmd_main_n','v_cmd_main_p','v_cmd_tmds_p','v_main_bias')):.3g} V |")
        elif k.startswith('quiescent'):
            rows.append(f"| {k} | - | - | {v.get('corner')} {v.get('temp_c')} C {v.get('vdd')} V | data | "
                        f"I(VDD) avg {abs(v.get('iavg', 0))*1e3:.3f} mA, max CMD {max(v.get('cmdmax', 0), v.get('cmdmax2', 0), v.get('pmax', 0)):.3g} V, "
                        f"max bias {max(v.get('biasmax', 0), v.get('tbiasmax', 0)):.3g} V |")
        elif k.startswith('ramp'):
            rows.append(f"| {k} | - | - | {v.get('corner')} {v.get('temp_c')} C | {'pass' if v.get('max_cmd_v', 9) < 0.5 else 'FAIL'} | "
                        f"max CMD {v.get('max_cmd_v', 0):.3g} V, max bias {v.get('max_bias_v', 0):.3g} V, peak I {v.get('peak_supply_current_a', 0)*1e3:.2f} mA |")
    rows.append('<!-- RESULTS:END -->')
    p = tools.HERE / 'README.md'
    t = p.read_text()
    block = '\n'.join(rows)
    if 'RESULTS_TABLE' in t:
        t = t.replace('RESULTS_TABLE', block)
    elif '<!-- RESULTS:BEGIN' in t:
        i = t.index('<!-- RESULTS:BEGIN'); j = t.index('<!-- RESULTS:END -->') + len('<!-- RESULTS:END -->')
        t = t[:i] + block + t[j:]
    p.write_text(t)


if __name__ == '__main__':
    e = build()
    print(json.dumps({k: v['state'] for k, v in e['tests'].items()}))
