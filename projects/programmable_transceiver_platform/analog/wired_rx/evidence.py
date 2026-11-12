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
        key=[('ring810M_quarter_3.24G_cm1_200mVpp', 'bit_errors', '0 errors, ring 810 MHz quarter rate 3.24 Gb/s, CM 1.0 V, 200 mVppd (all 8 samplers)'),
             ('ring625M_quarter_2.5G_cm1_200mVpp', 'bit_errors', '0 errors, ring 625 MHz quarter rate 2.5 Gb/s'),
             ('ring480M_quarter_1.92G_cm1_200mVpp', 'bit_errors', '0 errors, ring 480 MHz quarter rate 1.92 Gb/s'),
             ('ring810M_half_1.62G_cm1_200mVpp', 'bit_errors', '0 errors, ring 810 MHz half rate 1.62 Gb/s'),
             ('ring810M_full_0.81G_cm1_200mVpp', 'bit_errors', '0 errors, ring 810 MHz full rate 0.81 Gb/s'),
             ('ring480M_usbhs_0.48G_cm0.2_400mVpp', 'bit_errors', '0 errors USB HS 480 Mb/s (ring 480 MHz full rate), CM 0.2 V'),
             ('ring810M_quarter_3.24G_cm1_60mVpp_trimmed', 'bit_errors', '0 errors at 60 mVppd, trim p0 (non-gating)'),
             ('ring810M_quarter_3.24G_cm1_200mVpp', 'power_w', 'wired budget 16.1 mA (53 mW)'),
             ('offset_trim_p0', 'offset_mV_worst', 'trimmed residual < 20 mV (code p0)'),
             ('offset_trim0', 'offset_mV_worst', 'untrimmed offset (worst of 8 samplers); trimmed residual < 20 mV'),
             ('offset_trim_p3', 'input_referred_offset_mV', 'trim range +/-50 mV'),
             ('offset_trim_n3', 'input_referred_offset_mV', 'trim range +/-50 mV')],
        atb=[], status=['D0/E0/D1/E1 -> pt_wrx_cdr_loop raw_word / data_byte / early,late counters (SPI-readable)'],
        clocks=[],
        routes=[('wire_wmon_scope', 'open', 'front-end/CTLE waveform on WMON for scope slicing; bb_tap pending')],
        excluded=['r2 (2026-11-09): compact samplers (slicer_compact.py). Gating: ring 480/625/810 MHz x quarter/half/full '
                  'at 200 mVppd CM 1.0 V and USB HS 480 Mb/s (ring 480 MHz full rate) CM 0.2 V 400 mVppd, at every '
                  'envelope corner; for this block a corner failure fails clean. 3.6/4 Gb/s quarter is the non-gating '
                  'maxrate margin entry',
                  'Open loop: data centred on clock edge + 100 ps (assumed aperture, not measured); the window probe '
                  '(skew runs, non-gating) shifts the data against that instant. 40 quarter-UI per run, not a BER',
                  'Ideal ring clocks (P/40 edges, exact 45 deg); ring phase error, jitter and the clock-tree load of '
                  'the eight CKPk inputs are not included',
                  'Offset trim is 2+2 bits of switched capacitance per sampler, not a calibrated DAC',
                  'Noise and metastability not simulated']),
    detect=dict(
        key=[(f'usb_hs_squelch{s}', 'fraction_hit_above', f'fires on 150 mV diff (USB squelch edge), line CM {cm}')
             for s, cm in (('_cm-50', '-0.05 V'), ('', '0.2 V'), ('_cm500', '0.5 V'))]
            + [(f'usb_hs_squelch{s}', 'fraction_hit_below', f'silent on 100 mV diff, line CM {cm}')
               for s, cm in (('_cm-50', '-0.05 V'), ('', '0.2 V'), ('_cm500', '0.5 V'))]
            + [(f'usb_hs_disconnect{s}', 'fraction_hit_above', f'fires on 625 mV diff (USB disconnect edge), line CM {cm}')
               for s, cm in (('_cm-50', '-0.05 V'), ('', '0.2 V'), ('_cm360', '0.36 V'), ('_cm500', '0.5 V'))]
            + [(f'usb_hs_disconnect{s}', 'fraction_hit_below', f'silent on 525 mV diff, line CM {cm}')
               for s, cm in (('_cm-50', '-0.05 V'), ('', '0.2 V'), ('_cm360', '0.36 V'), ('_cm500', '0.5 V'))] + [
             ('rx_detect', 'inject_current_uA_est', '60-160 uA per leg (TX pad > Vse 0.8 V into 10 kohm)'),
             ('usb_hs_squelch', 'iavg', 'wired budget 4 mA')],
        atb=['atb_det_vref (ladder base 0.5 V)'], status=['DIFF_POS/DIFF_NEG/SE_P/SE_N sampled outputs -> RTL line-state, '
                                                          'squelch, disconnect, SE0, receiver-detect timing'], clocks=[],
        routes=[('wire_detect_via_wmon', 'open', 'line waveform on WMON via pt_wmon_sel; bb_tap pending')],
        excluded=['8-bit thresholds: 2-bit ladder taps (0/62.5/125/625 mV diff, 0.8/1.125/1.4/2.0 V SE)',
                  '6-bit test-current trim; 1 ms timeout/abort are RTL responsibilities',
                  'Envelope detector replaced by clocked comparators + digital window',
                  'Sampled on det_clk: FS/LS line state requires a running detect clock (>=48 MHz)']),
    ptrim=dict(
        key=[('code00', 'delay_ps_0', 'PH0 -> CKP0 delay at code 0 (810 MHz, 150 fF)'),
             ('code31', 'delay_ps_0', 'PH0 -> CKP0 delay at code 31')],
        atb=[], status=[], clocks=['PH0..7 in, CKP0..7 out (ring rate)'],
        routes=[('wire_cdr_phase_trim', 'open', 'per-phase 5-bit delay trim; calibration from edge histograms is digital')],
        excluded=['Code sweep judged by sims.ptrim_summary (step <= 1 deg at 810 MHz, monotonic, range >= 11.4 deg); '
                  'clock jitter added by the trim stages is not simulated']),
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
        excluded=['AC-3 (r-ac3): no phase interpolator; the RX pt_pll_ring runs with HOLD=1 (PFD in reset) from enable '
                  'in wired CDR mode and the per-bit pump legs (8..64 nA unit, 4 legs) on its loop-filter node are the only '
                  'loop actuator (FLL and PD on the same legs, no hand-over); pfd_mode=1 (HDMI/DVI) uses the PLL PFD',
                  'Extracted closed loop (pll_ring.ext + cdr.ext + slicer.ext) uses an analog-behavioural per-bit Alexander '
                  'PD stand-in (sample/holds + smooth XOR) with lat_extra ring cycles of delay; the capture-side PD circuit '
                  'is not in these runs',
                  'The FLL is not simulated: VCTRL and the filter integrator are pre-set to vc0 and the line rate is offset '
                  'from the measured free-running ring (free_*) by the case ppm',
                  'SSC is checked as a -400 ppm/us ramp over the run, not a full 33 kHz triangle',
                  'Each extracted result records the sha256 of the pll_ring/cdr/slicer netlists it used',
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
    closed = {k: v for k, v in (res.get('ac3') or res.get('closed') or {}).items() if isinstance(v, dict)}
    for k, v in closed.items():     # AC-3 free-running reference runs measure f1 only
        if k.startswith('free_'):
            v.setdefault('gating', False)
    clean_pass = (lay['drc_errors'] == 0 and lay['lvs_unique_match'] and gx.get('pass') and nom
                  and all(m.get('pass') for m in nom.values() if m.get('gating', True))
                  and all(m.get('pass') for m in closed.values() if m.get('gating', True)))
    corner_fail = sorted(f'{k}:{c}' for k, v in corners.items() for c, m in v.items() if not m.get('pass') and m.get('gating', True))
    if block == 'slicer':      # r2: the ring plan is qualified across the envelope, so corners gate clean
        clean_pass = bool(clean_pass) and not corner_fail
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
                         target='AC-3: 0 errors over > 2000 bits after settle with HOLD_PLL high throughout (free_*: f1 only)',
                         extracted_nominal={k: v for k, v in m.items() if _num(v) or isinstance(v, bool)}))
    for case, m in explore.items():
        perf.append(dict(case=case, metric='exploratory (non-gating, extracted tt/27C/3.3V)', target='above nominal rate',
                         extracted_nominal={k: v for k, v in m.items() if _num(v) or isinstance(v, bool)}))
    safe = res.get('safe', {})
    safe_pass = bool(safe) and all(m.get('pass') for m in safe.values() if m.get('gating', True))
    hashes = {}
    extra = ['slicer_compact.py', 'wrx_compact.py', 'generated/fast/ws_sa.spice', 'generated/fast/ws_ctl.spice'] if block == 'slicer' else []
    for rel in [f'{block}.spice', f'generated/{block}.ext.spice', f'generated/{block}.gds'] + COMMON + extra + (RTL if block == 'cdr' else []):
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
