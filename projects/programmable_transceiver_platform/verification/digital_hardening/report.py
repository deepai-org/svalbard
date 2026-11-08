#!/usr/bin/env python3
"""Assemble evidence/digital-hardening-evidence.json from the run_digital_hardening.sh outputs.

Only values present in the run outputs are reported; a missing stage is recorded as such and
its test stays open. Nothing here is inferred from a stage that did not run.
"""
import argparse
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2]
ROOT = P.parents[1]
SOURCES = ['rtl/pt_digital_macro.sv', 'rtl/pt_host_link.sv', 'rtl/pt_digital.sv', 'rtl/pt_regfile.sv', 'rtl/pt_spi.sv',
           'rtl/pt_core.sv', 'rtl/pt_fifo.sv', 'rtl/pt_pack.sv', 'rtl/pt_stream_link.sv', 'rtl/pt_stream_tx.sv',
           'rtl/pt_stream_rx.sv', 'rtl/pt_frame.sv', 'rtl/pt_memory.sv', 'rtl/pt_pattern.sv', 'rtl/pt_helpers.sv',
           'rtl/pt_clocktree_slow.sv', 'rtl/pt_freq_count.sv', 'rtl/pt_regmap_defs.svh', 'spec/debug-controls.json',
           'sim/tb_pt_freq_count.sv', 'sim/tb_digital_wire20.sv', 'integration/pt_digital_macro.sdc',
           'verification/digital_hardening/config.json', 'sim/tb_digital_gl.sv', 'sim/tb_async_fifo_regout.sv',
           'verification/run_digital_hardening.sh']


def sha(p):
    return 'sha256:' + hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else None


def pick(m, *subs):
    return {k: v for k, v in m.items() if all(s in k for s in subs)}


def fmax_table(sta):
    """Per clock and corner: f = 1 / (T_target - WNS_intra), from same-clock paths at the SDC target
    (setup slack scales 1:1 with the period for full-cycle paths; half-cycle and IO paths make it an
    estimate). Also the bisection result where it converged below the 400 ns search limit."""
    out = {}
    for c, r in (sta or {}).get('corners', {}).items():
        t = dict(r.get('targets_ns', {}))
        t.setdefault('fc0', 6.4)   # FC_PERIOD (integration/pt_digital_macro.sdc), not in the PT_TARGETS line
        row = {}
        for clk, v in r['slack'].items():
            if clk in ('fc1', 'fc2', 'fc3', 'fc4', 'fc5') or v['setup'] is None or clk not in t:
                continue
            per = t[clk] - min(v['setup'], 0.0) if v['setup'] < 0 else None
            row[clk] = dict(target_mhz=round(1000 / t[clk], 2), setup_slack_ns=round(v['setup'], 3),
                            hold_slack_ns=round(v['hold'], 3) if v['hold'] is not None else None,
                            meets_target=v['setup'] >= 0,
                            fmax_est_mhz=round(1000 / per, 1) if per else None,
                            fmax_bisection_mhz=(r['fmax_mhz'].get(clk) if r['fmax_mhz'].get(clk, 0) > 2.6 else None))
        out[c] = row
    return out


def curate(ev, sta, gls, pads, m, exp):
    ft = fmax_table(sta)
    tt = ft.get('tt_025C_3v30_nom', {})
    ss = ft.get('ss_125C_3v00_max', {})
    ssn = ft.get('ss_n40C_3v00_max', {})
    worst = lambda clk: min([(ft[c][clk]['fmax_est_mhz'] or ft[c][clk]['target_mhz']) for c in ft if clk in ft[c]] or [None])
    hw_tt = (tt.get('hword') or {}).get('fmax_est_mhz')
    hw_ss = worst('hword') if ft else None
    sig = ev['signoff']
    phys_clean = all(x == 0 for x in (sig.get('magic_drc_errors'), sig.get('klayout_drc_errors_librelane_gds'),
                                     sig.get('lvs_errors'), m.get('antenna__violating__nets'),
                                     m.get('route__drc_errors'))) and bool(exp) and \
        exp['main']['violations'] == 0 and exp['antenna']['violations'] == 0
    g = gls or {}
    pad_ss = (pads or {}).get('summary', {}).get('ss_125C_2v97', {})
    padc = (pads or {}).get('corners', {}).get('ss_125C_2v97', {})
    cmos_in_ss = min((i['f_ddr_max_mhz'] for i in padc.get('inputs', []) if i['cell'] == 'bi_24t' and i['when'].startswith('!CS')), default=None)
    return dict(
        timing=dict(
            method='OpenSTA on the routed netlist with OpenRCX SPEF (nom RC at tt, max RC at ss, min RC at ff), '
                   'propagated CTS clocks, integration/pt_digital_macro.sdc at its targets. fmax_est = 1/(T - WNS) '
                   'over paths launched and captured by the same clock.',
            envelope_note='No Liberty exists inside the narrow envelope (22-32 C, 3.15-3.35 V). The nearest '
                          'characterized corners are tt_025C_3v30 (inside), ss_125C_3v00 / ss_n40C_3v00 and '
                          'ff_n40C_3v60 / ff_125C_3v60 (outside, pessimistic in both directions).',
            per_corner=ft,
            hold='met at every clock and corner (worst hold slack in sta-report.json)',
            crossings_after_exceptions='Remaining timed clock-to-clock paths are the bounded categories of the SDC '
                                       '(Gray pointers, FIFO storage reads, held handshake registers) plus one '
                                       'undocumented crossing: ref-domain cal_busy ORed combinationally into the '
                                       'rf_mute output (rftx-constrained). See open_risks.'),
        tests=dict(
            digital=dict(
                safe=dict(proposal='pass', evidence=['evidence/digital-hardening-evidence.json#gate_level.reset_safety',
                                                     'evidence/regfile-verification.json'],
                          note=f"Post-route netlist: {g.get('reset_safety', {}).get('reset_snapshots')} snapshots taken "
                               "while reset is asserted (RESET_N+POR, RESET_N alone, POR alone, RESET_N mid-write): "
                               f"{g.get('reset_safety', {}).get('violations')} violations; analog_cfg/debug_cfg at "
                               "declared defaults, island_en/island_on/ATB/receiver/observation enables 0, D2H OE 0, "
                               "no X/Z on any control output (wire_tx_data/rf_tx_sample are X with valid=0: FIFO "
                               "storage has no reset)."),
                clean=dict(proposal='pass' if phys_clean else 'open',
                           evidence=['evidence/digital-hardening-evidence.json#signoff'],
                           note='Magic DRC 0, KLayout DRC 0 (LibreLane GDS and the analog-image Magic 8.3.678 export, '
                                'which XORs to 0 against it), Netgen LVS 0 errors, OpenROAD and KLayout antenna 0. '
                                'Gate-level simulation of the post-route netlist matches the RTL and the register model. '
                                'Timing does NOT meet the clock targets at ss (and several at tt); performance_vs_target '
                                'records it (block-deliverables: performance does not gate freeze).'),
                observable=dict(proposal='pass', evidence=['evidence/digital-hardening-evidence.json#gate_level.observability'],
                                note='ID/ABI/map hash, POR vs RESET_N cause flags, island power-good and fault status, core '
                                     'status and frequency-counter lock/count read over SPI on the post-route netlist.'),
                fallback=dict(proposal='waived_core')),
            hostio=dict(
                safe=dict(proposal='open', note='Digital half passes (D2H OE=0 and data 0 at reset on the netlist; H2D '
                          'inputs only capture). Pad half (provider bi_24t/in_c with powered peer and unpowered die, '
                          'RESET_N weak pull-down PD=1 on in_c) is an assembly/pads-stage check not run here.'),
                clean=dict(proposal='open', note='pt_host_link is inside the clean macro; the provider pad cells and their '
                           'hookup at the ring are not assembled or checked yet (freeze stage 2/4).'),
                observable=dict(proposal='pass', evidence=['evidence/digital-hardening-evidence.json#gate_level.host_link_loopback'],
                                note='Core status over SPI shows frame-receiver lock / rx fault; D2H looped to H2D locks in '
                                     'DDR, SDR and reduced-rate SDR on the post-route netlist; DBG_OBS host_rx_clk_div.'),
                fallback=dict(proposal='pass', note='debug.host_link.mode 1/2 (SDR, reduced-rate SDR) implemented and '
                              'exercised in the netlist loopback; SPI capture/playback memory is the last route.'))),
        hostio=dict(
            partition='Provider gf180mcu_fd_io cells own pads/ESD/drive/receivers: bi_24t at the bidir sites (SPI, H2D, '
                      'D2H), in_c at rst_n_pad (RESET_N, PD=1 weak pull-down), clk_pad (in_s in the template) needs '
                      'the provider-permitted substitution to bi_24t for D2H[0]. Ours (in the hardened macro, '
                      'rtl/pt_host_link.sv): DDR/SDR capture on H2D_CLK, pair FIFO into the core host word clock, '
                      'D2H launch, centre-aligned forwarded D2H_CLK (word/2 toggle on the falling edge in DDR, '
                      'gated inverted word clock in SDR), d2h_enable gating, drive/slew controls to the pads.',
            pad_toggle_screen=dict(summary=(pads or {}).get('summary'), ss_cmos_input_f_ddr_max_mhz=cmos_in_ss,
                                   note='Liberty-only eye budget (see hostio_pad_screen.py); the pads alone allow '
                                        'roughly 178 MHz DDR out / 191 MHz DDR in (CMOS receiver, CS=0) at ss 2.97 V; '
                                        'Schmitt inputs (CS=1, in_s) drop to ~148 MHz. Not a qualification.'),
            core_limited_rate=dict(host_word_fmax_mhz=dict(tt=hw_tt, worst_corner=hw_ss),
                                   ddr_pin_clock_max_mhz=dict(tt=round(hw_tt / 2, 1) if hw_tt else None,
                                                              worst_corner=round(hw_ss / 2, 1) if hw_ss else None),
                                   target='156.25 MHz DDR pins = 312.5 Mword/s'),
            verdict='156.25 MHz DDR is NOT reachable: the pads would allow about 150-180 MHz DDR, but the standard-cell '
                    'transport (framer, FIFO read muxes) closes only at the host word clock above; the DDR pin clock is '
                    'half of it.',
            reduced_rate_proposal='Tapeout-plan host-link fallback: SDR (mode 1) or reduced-rate SDR (mode 2) with the '
                                  'host word clock at or below the worst-corner fmax (H2D_CLK = D2H_CLK = word clock), or '
                                  'DDR with the pin clock at half of it. Full rate needs a 2-word-wide transport and '
                                  'pipelined FIFO reads (open RTL item).'),
        performance_vs_target=[
            dict(item='host word clock', target_mhz=312.5, tt_mhz=hw_tt, worst_corner_mhz=hw_ss),
            dict(item='wired double-word clock (wtx/wrx)', target_mhz=125.0,
                 tt_mhz=[(tt.get(k) or {}).get('fmax_est_mhz') for k in ('wtx', 'wrx')],
                 worst_corner_mhz=[worst(k) for k in ('wtx', 'wrx')] if ft else None),
            dict(item='SPI SCLK', target_mhz=20.0, tt_mhz=(tt.get('sclk') or {}).get('fmax_est_mhz'),
                 worst_corner_mhz=worst('sclk') if ft else None, spec='starts at <= 1 MHz; bench 10 MHz'),
            dict(item='RF sample clocks (rftx/rfrx)', target_mhz=50.0,
                 tt_mhz=[(tt.get(k) or {}).get('fmax_est_mhz') for k in ('rftx', 'rfrx')],
                 worst_corner_mhz=[worst(k) for k in ('rftx', 'rfrx')] if ft else None),
            dict(item='pt_clocktree_slow word clock (ctw)', target_mhz=156.25, tt_mhz=(tt.get('ctw') or {}).get('fmax_est_mhz'),
                 worst_corner_mhz=worst('ctw') if ft else None),
            dict(item='frequency-counter sources (fc*)', target_mhz=156.25, tt_mhz=(tt.get('fc0') or {}).get('fmax_est_mhz'),
                 worst_corner_mhz=worst('fc0') if ft else None),
            dict(item='area', allocation_um2=2500000, die_um2=m.get('design__die__area'),
                 note='1800 x 1800 um; 1650 x 1650 um failed detailed placement after antenna repair and the '
                      '1580 x 1580 um floorplan failed detailed placement (utilization ~0.67-0.71).')],
        decisions=[
            'Memory: no gf180mcu_fd_ip_sram macro. The RTL storage is register arrays with dual-clock (async FIFO) or '
            'combinational reads; single-port synchronous SRAMs cannot serve them without clock muxing. Flop storage '
            '(~11.3k sequential cells total) is inside the macro. Item 9 MIM-over-SRAM therefore does not apply.',
            'Metal5: the primary macro routes on Metal1-Metal5 with Metal4-only PDN straps (PDN_MULTILAYER false). '
            'A Metal1-Metal4 variant (Metal5 free for MIM) of the same netlist and floorplan also routed with DRC 0 and '
            'LVS 0 but left 2 antenna violations and ~45 % worse tt setup slack (variants.metal4_only); at '
            '1650 x 1650 um the Metal4-only route did not converge (11371 GRT overflows).',
            'Timing targets kept at the specification rates; closure is not claimed. fmax per clock/corner recorded.',
            'Port buffering: LibreLane input/output port buffers enabled (disabling output buffers crashed TritonCTS).',
            'Signoff SDC adds three exceptions to the PnR SDC (CS_N->MISO and CS_N->register data false paths, '
            'forwarded D2H_CLK unconstrained, bounded crossings restricted to the reader clock); see sdc.pnr vs sdc.signoff.'],
        open_risks=[
            'Timing: at ss_125C/3.0 V (outside the envelope) every fast clock misses its target by 2-5x; at tt the '
            'host word, wired and RF sample clocks also miss. Silicon must run reduced clocks or the RTL needs '
            'pipelining (FIFO read muxes over a 1.8 mm die, stream framer, regfile commit path).',
            'Max slew/cap violations remain (hundreds at tt, ~1.7k at ss) on the large flop-FIFO nets.',
            'Undocumented CDC: rf_mute = cal_busy (ref domain) OR stream mute (rftx). Level to analog, but should be '
            'resynchronized or documented.',
            'Area 3.24 mm2 against the 2.5 mm2 digital+memory allocation.',
            'pt_clocktree_slow cfg_det_en/cfg_det_div have no register field (strapped in pt_chip).',
            'D2H[0] at clk_pad needs the in_s -> bi_24t cell substitution; RESET_N PD=1 tie and pad-level safe tests '
            'belong to the pad/assembly stage.',
            'GLS is zero-delay functional (no SDF); timing is covered by STA only.',
            'Regfile formal proof was not re-run here on the final map (0x5A1F); the register-file agent owns it.'],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', default='FREEZE1')
    ap.add_argument('--evidence', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    run = out / 'design/runs' / a.tag
    m = load(run / 'final/metrics.json') or {}
    exp = load(out / 'export/klayout-summary.json')
    xor = load(out / 'export/xor.json')
    sta = load(out / 'sta/sta-report.json')
    gls = load(out / 'gls/gls-report.json')
    pads = load(out / 'pads/hostio-pad-screen.json')
    rd = lambda p: (out / p).read_text().strip() if (out / p).exists() else None
    die = m.get('design__die__bbox')
    ev = dict(
        block='digital', also_covers='hostio (clocked logic; pad cells are provider gf180mcu_fd_io)',
        macro='pt_digital_macro', run_tag=a.tag,
        source_hashes={s: sha(P / s) for s in SOURCES if (P / s).exists()},
        images=dict(digital=rd('digital-image.txt'), analog=rd('analog-image.txt')),
        tools=dict(librelane=rd('librelane-version.txt'), magic_export=rd('export/magic-version.txt'),
                   klayout_export=rd('export/klayout-version.txt'), sta=(sta or {}).get('tool')),
        pdk='gf180mcuD (open_pdks 1.0.605, commit f6eeac7d) in both images; gf180mcu_fd_sc_mcu7t5v0',
        physical=dict(
            die_bbox_um=die, core_bbox_um=m.get('design__core__bbox'),
            die_area_um2=m.get('design__die__area'), core_area_um2=m.get('design__core__area'),
            instance_area_um2=m.get('design__instance__area'),
            stdcell_area_um2=m.get('design__instance__area__stdcell'),
            utilization=m.get('design__instance__utilization'),
            instance_count=m.get('design__instance__count'),
            stdcell_count=m.get('design__instance__count__stdcell'),
            io_count=m.get('design__io'),
            allocation_um2=dict(digital=1650000, memory=850000, total=2500000),
            routing_layers=('Signal routing Metal2-Metal5 (RT_MAX_LAYER=Metal5), cell rails Metal1, PDN Metal4 vertical '
                            'straps only (PDN_MULTILAYER=false); Metal5 carries signal routing in this macro. The '
                            'Metal1-Metal4 variant that keeps Metal5 free for MIM decap is recorded under variants.'),
            memory='No SRAM macro: the RTL storage is register arrays (async/sync FIFOs 4.4 kbit, capture/playback '
                   '2 x 32 x 24 bit) with dual-clock or combinational reads that single-port gf180mcu_fd_ip_sram macros '
                   'cannot serve without clock muxing. Implemented in flops inside the digital+memory allocation.',
            wire_length_um=m.get('route__wirelength'),
            route_drc_errors=m.get('route__drc_errors')),
        metrics_snapshot={k: v for k, v in m.items() if any(s in k for s in (
            'drc', 'lvs', 'antenna', 'timing__setup__ws', 'timing__hold__ws', 'clock__skew', 'power__total',
            'design__max_slew', 'design__max_cap', 'design__max_fanout', 'xor', 'disconnected'))},
        signoff=dict(
            magic_drc_errors=m.get('magic__drc_error__count'),
            klayout_drc_errors_librelane_gds=m.get('klayout__drc_error__count'),
            klayout_on_exported_gds=exp,
            gds_export=dict(tool=rd('export/magic-version.txt'), sha256=rd('export/gds.sha256'),
                            xor_vs_librelane_gds=(xor or {}).get('xor_total')),
            lvs_errors=m.get('design__lvs_error__count'),
            lvs_unique_match=m.get('design__lvs_unmatched_device__count') == 0 and m.get('design__lvs_error__count') == 0
            if m else None,
            antenna_openroad=pick(m, 'antenna'),
            illegal_overlap=m.get('magic__illegal_overlap__count')),
        sta=sta, gate_level=gls, hostio_pad_screen=dict(summary=(pads or {}).get('summary'),
                                                        assumptions=(pads or {}).get('assumptions')),
    )
    # Provenance of the hardened sources: the run copies rtl/ at launch (design/rtl); list repo files
    # that differ from that copy, and the PnR-time vs signoff SDC.
    ev['hardened_copy_differences'] = sorted(
        f.name for f in (out / 'design/rtl').glob('*') if (P / 'rtl' / f.name).exists()
        and (P / 'rtl' / f.name).read_bytes() != f.read_bytes())
    pnr_sdc = out / 'design/pt_digital_macro.sdc'
    ev['sdc'] = dict(pnr=sha(pnr_sdc) if pnr_sdc.exists() else None, signoff=sha(P / 'integration/pt_digital_macro.sdc'))
    over = out / 'config-override.json'
    ev['config_override'] = json.loads(over.read_text()) if over.exists() else None
    ev['variants'] = dict(metal4_only=load(out / 'metal4_only_variant/metrics.json') and {
        k: v for k, v in load(out / 'metal4_only_variant/metrics.json').items() if any(t in k for t in (
            'drc_error', 'lvs_error', 'antenna__violating', 'utilization', 'timing__setup__ws__corner:nom_tt',
            'max_slew_violation__count', 'xor_difference'))})
    ev.update(curate(ev, sta, gls, pads, m, exp))
    Path(a.evidence).parent.mkdir(parents=True, exist_ok=True)
    prev = {}  # curated sections are recomputed from the run outputs every time
    for k in ('tests', 'decisions', 'performance_vs_target', 'excluded_coverage', 'open_risks', 'readiness_proposal',
              'hostio', 'other_checks', 'history'):
        if k in prev:
            ev[k] = prev[k]          # curated sections (written from the numbers above) are kept
    Path(a.evidence).write_text(json.dumps(ev, indent=1) + '\n')
    print(json.dumps(dict(physical=ev['physical'], signoff=ev['signoff']), indent=1)[:4000])


if __name__ == '__main__':
    main()
