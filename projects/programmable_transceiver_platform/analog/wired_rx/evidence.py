"""Per-block four-test evidence records (spec/block-deliverables.md schema)."""
import json
import math
from pathlib import Path

import wrx_flow as f

RTL = ['rtl/pt_wrx_cdr_loop.sv', 'rtl/tb_pt_wrx_cdr_loop.sv']
COMMON = ['netlists.py', 'wrx_flow.py', 'sims.py', 'run_family.py', 'evidence.py', 'run_wired_rx.sh']

META = dict(
    termination=dict(
        key=[('modes', 'vcm_div', 'TERM_VCM 1.2 V (serial CM shunt mode)'),
             ('modes', 'vcm_gnd_ron_ohm', 'USB HS ground switch << 45 ohm (<3 ohm used)'),
             ('modes', 'vcm_settle_ns', 'settle (stopped-only selection)'),
             ('modes', 'idd_div', 'wired budget 8 mA')],
        atb=['TERM_VCM (block output; tap directly)'], status=[], clocks=[],
        routes=[('wire_board_termination', 'pass', 'term_mode=00 (or term_en=0): TERM_ENABLE=DIFF_ENABLE=0, TERM_VCM grounded; '
                 'board resistors take over. Simulated in modes case (te_off, de_div) and safe off cases.')],
        excluded=['6-bit termination trim (pad bank has no trim legs; analog/pads owns the resistors)',
                  'Pad-bank resistance/matching: owned and extracted by analog/pads',
                  'TERM_VCM driver is a 1.75k/1k divider (636 ohm Thevenin) with ~1.8 pF: sets DC CM for AC-coupled '
                  'or self-biased sources; it cannot absorb DC common-mode current of a DC-coupled source (use diff mode)']),
    rxlevel=dict(
        key=[('bbm', 'bbm_gap_byp_to_div_ns', 'break-before-make gap > 0'),
             ('bbm', 'bbm_gap_div_to_byp_ns', 'break-before-make gap > 0'),
             ('bbm', 'idd_static', 'wired budget 0.05 mA (bleed of the active output)')],
        atb=[], status=[], clocks=[],
        routes=[('wire_wmon_scope', 'open', 'RX_P/RX_N (rxlevel output) selectable on WMON via pt_wmon_sel codes 00/01; '
                 'needs the shared bb_tap buffer (rf_rx agent) and the WMON pad.')],
        excluded=['Divider/bypass resistors and switches are pad-resident (analog/pads wired_receive); only their control is here',
                  'Gate loads modelled as 1.0 pF (bypass) / 0.4 pF (divider) ideal capacitors, not the extracted pad']),
    rxselect=dict(
        key=[('ac_direct0', 'bw3db', 'SLICER_INPUT path BW (150 fF load) >= 1.5 GHz'),
             ('ac_direct1', 'bw3db', 'direct (USB HS) path BW'),
             ('ac_off', 'g1g', 'off isolation at 1 GHz < -20 dB')],
        atb=[], status=[], clocks=[],
        routes=[('wire_wmon_scope', 'open', 'RX_P/N and CTLE_P/N observable on WMON through pt_wmon_sel (independent cell); '
                 'needs bb_tap + WMON pad.')],
        excluded=['Source-follower isolation in the architecture topology string replaced by plain transmission gates']),
    wmon_sel=dict(
        key=[('ac_sel0', 'bw3db', 'WMON source path BW into 300 fF bb_tap input'),
             ('ac_sel2', 'bw3db', 'CTLE_P to WMON_IN BW'), ('ac_off', 'g1g', 'off isolation')],
        atb=['WMON_IN (observation node itself)'], status=[], clocks=[],
        routes=[('wire_wmon_scope', 'open', 'selector implemented and simulated; bb_tap buffer and WMON pad pending'),
                ('wire_detect_via_wmon', 'open', 'same selector; FPGA decides line state from the WMON waveform')],
        excluded=['bb_tap buffer itself (rf_rx agent shared design, consolidation item 7)']),
    ctle=dict(
        key=[('ac_code1', 'gdc', 'dc_gain 1.0 (0 dB)'), ('ac_code0', 'gdc', 'DC gain, least peaking'),
             ('ac_code3', 'peaking_db', 'peaking ~6 dB (zero 0.8 GHz / pole 1.66 GHz)'),
             ('ac_code2', 'peaking_db', 'mid peaking'), ('ac_code1', 'g1g25', 'gain at 1.25 GHz (2.5 Gb/s Nyquist)'),
             ('ac_code0', 'idd_a', 'wired budget 12 mA'), ('ac_code3', 'g2g5', '5 Gb/s stretch: gain at 2.5 GHz (non-gating)'), ('ac_bypass', 'g1g25', 'bypass loss at 1.25 GHz'),
             ('ac_bypass', 'bw3db', 'bypass path BW')],
        atb=['atb_ctle_pbias (PMOS tail gate)', 'atb_ctle_src (source node / output CM monitor)'], status=[], clocks=[],
        routes=[('wire_ctle_bypass', 'pass', 'wire_ctle_bypass=1: amplifier and loads off, 2x(20+20 um) TGs connect RX->CTLE '
                 'outputs; simulated (ac_bypass). External board equalizer optional.')],
        excluded=['Speed pass: input pair 48 um (was 80) and single bypass TG to cut RX_P loading (302 -> ~180 fF)',
                  'Input CM below ~0.5 V (USB HS) is out of range: use rxselect_direct=1 or the bypass',
                  'Equalization quality vs channel (eye) not simulated; AC response only']),
    slicer=dict(
        key=[('data_1G_cm1_200mVpp', 'bit_errors', '0 errors at 1 Gb/s (gating rate), CM 1.0 V, 200 mVppd, quarter-rate'),
             ('data_1G_cm1_200mVpp', 'sampling_delay_ps', 'CK0 edge to D0 decision instant (divider + aperture)'),
             ('data_1G_cm1_60mVpp_trimmed', 'bit_errors', '0 errors at 1 Gb/s, 60 mVppd, trim n1'),
             ('data_0.48G_cm0.2_400mVpp', 'bit_errors', '0 errors USB HS 480 Mb/s, CM 0.2 V'),
             ('data_1G_cm1_200mVpp', 'power_w', 'wired budget 16.1 mA (53 mW)'),
             ('offset_trim_p0', 'offset_mV_worst', 'trimmed residual < 20 mV (code p0)'),
             ('offset_trim0', 'offset_mV_worst', 'untrimmed offset (worst of 4 samplers); trimmed residual < 20 mV'),
             ('offset_trim_p3', 'input_referred_offset_mV', 'trim range +/-50 mV'),
             ('offset_trim_n3', 'input_referred_offset_mV', 'trim range +/-50 mV')],
        atb=[], status=['D0/E0/D1/E1 -> pt_wrx_cdr_loop raw_word / data_byte / early,late counters (SPI-readable)'],
        clocks=[],
        routes=[('wire_wmon_scope', 'open', 'front-end/CTLE waveform on WMON for scope slicing; bb_tap pending')],
        excluded=['Gating line rate 1 Gb/s (serial) and 480 Mb/s (USB HS); higher rates are reported per corner in the '
                  'maxrate entry (non-gating). The quarter-rate divider flops limit the rate (setup of the divider '
                  'links), most at the ss corner',
                  'Divider/sampler phase spacing depends on matched clock-to-Q of the four divider flops (not trimmed)',
                  '97 boundary phase slots + 8 burst samplers of the architecture model: replaced by 8 quarter-rate samplers '
                  '(half-rate bang-bang); burst acquisition not implemented',
                  'Offset trim is 2+2 bits of switched capacitance per sampler, not a calibrated DAC',
                  'Noise and metastability not simulated']),
    detect=dict(
        key=[('usb_hs_squelch', 'fraction_hit_above', 'fires on 200 mV diff (> 125 mV threshold)'),
             ('usb_hs_squelch', 'fraction_hit_below', 'silent on 60 mV diff (squelch)'),
             ('usb_hs_disconnect', 'fraction_hit_above', 'fires on 800 mV diff (625 mV threshold)'),
             ('usb_hs_disconnect', 'fraction_hit_below', 'silent on 400 mV diff'),
             ('rx_detect', 'inject_current_uA_est', '100 uA per leg'),
             ('usb_hs_squelch', 'iavg', 'wired budget 4 mA')],
        atb=['atb_det_vref (ladder base 0.5 V)'], status=['DIFF_POS/DIFF_NEG/SE_P/SE_N sampled outputs -> RTL line-state, '
                                                          'squelch, disconnect, SE0, receiver-detect timing'], clocks=[],
        routes=[('wire_detect_via_wmon', 'open', 'line waveform on WMON via pt_wmon_sel; bb_tap pending')],
        excluded=['8-bit thresholds: 2-bit ladder taps (0/62.5/125/625 mV diff, 0.8/1.125/1.4/2.0 V SE)',
                  '6-bit test-current trim; 1 ms timeout/abort are RTL responsibilities',
                  'Envelope detector replaced by clocked comparators + digital window',
                  'Sampled on det_clk: FS/LS line state requires a running detect clock (>=48 MHz)']),
    cdr=dict(
        key=[('acq', 'i_ibpll_uA', 'PLL charge-pump bias delivered in acquisition (10 uA)'),
             ('hold_idle', 'i_ibpll_uA', 'PLL charge pump disabled in hold (0)'),
             ('hold_up', 'i_bb_nA', 'bang-bang pump up current (~50 nA)'),
             ('hold_dn', 'i_bb_nA', 'bang-bang pump down current (~-50 nA)'),
             ('hold_up_g', 'i_bb_nA', 'bb_gain=1 (~100 nA)'),
             ('hold_idle', 'i_vdd_uA', 'cell supply current incl. hand-over flops clocked by FBCK (39 MHz)')],
        atb=['atb_cdr_pbias (PMOS reference gate)', 'VCTRL is the pt_pll_ring ATB_VCTRL node (timing tap)'],
        status=['freq_hold, phase_sel, early/late counters (pt_wrx_cdr_loop)'],
        clocks=['QCK / RX ring FBCK -> WCLK_OBS via clk_obs (timing)'],
        routes=[('wire_cdr_external_clock', 'open', 'WCLK_IN path: diff_clk_rx -> ring PLL reference or slicer clocks is an '
                 'integration item'),
                ('wire_cdr_fpga_oversample', 'open', 'cfg_raw=1 streams all eight samples per ring cycle (RTL simulated); '
                 'D2H transport pending')],
        excluded=['Phase interpolator removed (lead decision): dual-loop CDR on a second pt_pll_ring instance (timing '
                  'family, instantiated unchanged at integration) for half/quarter rate; full rate uses 8x oversampling '
                  'with digital blind phase picking (no analog tracking)',
                  'The bang-bang pump is a separate weak pump on the PLL loop-filter node (ATB_VCTRL), not the PLL\'s own '
                  'pump: freq_hold gates its REF (at an FBCK falling edge) and clamps its pump bias IB_PLL; the pt_pll_ring '
                  'HOLD input (timing r6) is tied low and not used yet',
                  'Extracted closed loop uses an analog-behavioural phase detector (sample/holds + smooth logic, ~4 ns '
                  'decision filter) as a stand-in for the RTL, which decides every 20-bit word; long windows, ppm, SSC '
                  'and the frequency-counter hand-over (FLL) are behavioural (RTL + analog loop model)',
                  'The FLL hand-over step (cfg_fll_en) needs >100 us of ring time and is not simulated extracted',
                  'Cold acquisition is not simulated: VCTRL is pre-charged near the 625 MHz lock value before the '
                  'frequency loop runs',
                  'Each extracted result records the sha256 of the pll_ring.ext.spice it used',
                  'Ring port phase error of pt_pll_ring (timing evidence) is included in the extracted runs as-is',
                  'Ring-rate capture is the fast-cell block pt_wrx_cap (capture.py), which is not part of this evidence flow']),
)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def write(block, res):
    meta = META[block]
    lay = res['layout']
    sims = res.get('sims', {})
    nom_key = 'ext_typical_27C_3.3V'
    nom = sims.get(nom_key, {})
    sch = sims.get('sch_typical_27C_3.3V', {})
    corners = {k: v for k, v in sims.items() if k.startswith('ext_') and k != nom_key}
    gx = lay.get('gds_export', {})
    closed = {k: v for k, v in res.get('closed', {}).items() if isinstance(v, dict)}
    clean_pass = (lay['drc_errors'] == 0 and lay['lvs_unique_match'] and gx.get('pass') and nom
                  and all(m.get('pass') for m in nom.values() if m.get('gating', True))
                  and all(m.get('pass') for m in closed.values() if m.get('gating', True)))
    corner_fail = sorted(f'{k}:{c}' for k, v in corners.items() for c, m in v.items() if not m.get('pass') and m.get('gating', True))
    nongating_fail = sorted(f'{k}:{c}' for k, v in sims.items() for c, m in v.items() if not m.get('pass') and not m.get('gating', True))
    explore = res.get('explore', {})
    perf = []
    for case, metric, target in meta['key']:
        vals = [v.get(case, {}).get(metric) for v in corners.values()]
        nums = [x for x in vals if _num(x)]
        perf.append(dict(case=case, metric=metric, target=target,
                         extracted_nominal=nom.get(case, {}).get(metric), schematic_nominal=sch.get(case, {}).get(metric),
                         corner_min=min(nums) if nums else None, corner_max=max(nums) if nums else None,
                         corners_reported=len(nums)))
    mr = res.get('maxrate', {})
    if mr:
        table = {}
        for cor, cases in mr.items():
            ok = [c for c, m in cases.items() if m.get('pass')]
            rates = {c: (m.get('line_rate_bps') or None) for c, m in cases.items()}
            table[cor] = dict(passing=sorted(ok), failing=sorted(c for c in cases if c not in ok))
        perf.append(dict(case='maxrate', metric='rate sweep per corner (extracted, non-gating)', target=
                         '2.5 Gb/s line (1.25 GHz half-rate clocks)', per_corner=table))
    for case, m in closed.items():
        perf.append(dict(case=case, metric='extracted CDR run (pll_ring.ext + cdr.ext [+ slicer.ext], tt)' +
                         ('' if m.get('gating', True) else ' [non-gating]'),
                         target='acq: lock within 3000 ppm, BB steps of the right sign; track/dual: 0 errors after settle',
                         extracted_nominal={k: v for k, v in m.items() if _num(v) or isinstance(v, bool)}))
    for case, m in explore.items():
        perf.append(dict(case=case, metric='exploratory (non-gating, extracted tt/27C/3.3V)', target='above nominal rate',
                         extracted_nominal={k: v for k, v in m.items() if _num(v) or isinstance(v, bool)}))
    safe = res.get('safe', {})
    safe_pass = bool(safe) and all(m.get('pass') for m in safe.values() if m.get('gating', True))
    hashes = {}
    for rel in [f'{block}.spice', f'generated/{block}.ext.spice', f'generated/{block}.gds'] + COMMON + (RTL if block == 'cdr' else []):
        p = f.HERE / rel
        if p.exists():
            hashes[rel] = f.sha256(p)
    routes = [dict(route=r, state=s, notes=n) for r, s, n in meta['routes']]
    fb_state = 'pass' if routes and all(r['state'] == 'pass' for r in routes) else 'open'
    ev = dict(
        block=block, subckt=lay['subckt'], source_hashes=hashes,
        images=dict(analog=f.ANALOG_IMAGE, analog_ref=f.ANALOG_REF, digital=f.DIGITAL_IMAGE, digital_tag=f.DIGITAL_TAG,
                    digital_note='rebuilt canary (not byte-identical to locked 9253a51f...)'),
        pdk=f.PDK_REVISION,
        tests=dict(
            safe=dict(state='pass' if safe_pass else ('fail' if safe else 'open'),
                      cases=[dict(case=k, **{kk: vv for kk, vv in v.items() if _num(vv) or isinstance(vv, bool)})
                             for k, v in safe.items()],
                      notes='Extracted netlist. off_*: rail 3.63 V, all controls low, clocks running, analog inputs 3.3 V, '
                            '0/27/85 C. stuck_on: all controls high at 3.63 V (no latch/short, current bounded). '
                            'unpowered: rail via 1 Mohm, controls 0 (register isolation clamp), clocks running, '
                            'pad-reachable inputs (detect TX_P/N) 3.63 V, internal analog nodes 0 V. '
                            'unpowered_internal_driven is non-gating: internal RX/CTLE nodes forced to 3.63 V (only possible '
                            'if the pad bypass were on with this island off) back-drive the rail through PMOS TG wells. '
                            'Pad-level stress and brownout ramps are analog/pads scope.'),
            clean=dict(state='pass' if clean_pass else 'fail',
                       drc=dict(tool='magic 8.3.623 drc(full)', errors=lay['drc_errors'],
                                klayout_gf180_on_exported_gds=gx.get('klayout_drc'),
                                gds_export=dict(magic=gx.get('magic'), image=gx.get('image'),
                                                marker_shapes=gx.get('marker_shapes'), hres_ok=gx.get('hres_ok'))),
                       lvs=dict(tool='netgen 1.5.316 gf180mcuD_setup.tcl', unique_match=lay['lvs_unique_match'],
                                final=lay['lvs_final'], devices=lay['devices']),
                       extracted_nominal={c: {k: v for k, v in m.items() if _num(v) or isinstance(v, bool)}
                                          for c, m in nom.items()},
                       corner_failures=corner_fail, non_gating_failures=nongating_fail,
                       area=dict(size_um=lay['size_um'], area_um2=lay['area_um2'], ceiling_um2=lay['area_ceiling_um2'])),
            observable=dict(state='open', atb_taps=meta['atb'], status_bits=meta['status'], clock_obs=meta['clocks'],
                            notes='Taps/status are exposed at block ports; atb_tap cells, register-map entries and '
                                  'clk_obs hookup are added at integration (not yet available).'),
            fallback=dict(state=fb_state, routes=routes, bypass_loading_fF=res.get('bypass_loading_fF'))),
        performance_vs_target=perf,
        corner_set='tt/ss/ff x 22/32 C x 3.15/3.35 V (spec/tapeout-plan.md operating envelope), extracted netlist',
        excluded_coverage=meta['excluded'])
    if block == 'cdr' and 'rtl' in res:
        ev['rtl_check'] = res['rtl']
    (f.GENERATED / f'{block}-evidence.json').write_text(json.dumps(ev, indent=1, default=str) + '\n')
    return ev
