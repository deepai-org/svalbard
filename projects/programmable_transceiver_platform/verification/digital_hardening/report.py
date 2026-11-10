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
           'rtl/pt_dense_header.sv', 'rtl/pt_core.sv', 'rtl/pt_core_pair.sv', 'rtl/pt_dense_pair.sv', 'rtl/pt_dense_pair_link.sv',
           'rtl/pt_pair_gearbox.sv', 'rtl/pt_fifo.sv', 'rtl/pt_memory.sv', 'rtl/pt_pattern.sv', 'rtl/pt_helpers.sv',
           'rtl/pt_clocktree_slow.sv', 'rtl/pt_freq_count.sv', 'rtl/pt_regmap_defs.svh', 'spec/debug-controls.json',
           'sim/tb_pt_freq_count.sv', 'sim/tb_digital_wire20.sv', 'sim/reference/pt_dense_transport.sv', 'integration/pt_digital_macro.sdc',
           'verification/digital_hardening/config.json', 'sim/tb_digital_gl.sv', 'sim/tb_async_fifo_regout.sv',
           'verification/run_digital_hardening.sh', 'verification/digital_hardening/report.py',
           'verification/digital_hardening/Dockerfile', 'verification/digital_hardening/prepare_toolchain.py',
           'verification/digital_hardening/gls.sh', 'verification/digital_hardening/gls_check.py',
           'verification/digital_hardening/sta_signoff.py']


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
    """Derive current verdicts only from the supplied run's measurements."""
    ft = fmax_table(sta)
    rows = [row for clocks in ft.values() for row in clocks.values()]
    hold = [row['hold_slack_ns'] for row in rows]
    setup_met = bool(rows) and all(row['meets_target'] for row in rows)
    hold_met = bool(hold) and all(value is not None and value >= 0 for value in hold)
    sig = ev['signoff']
    physical_checks = {
        'magic': sig.get('magic_drc_errors'),
        'klayout': sig.get('klayout_drc_errors_librelane_gds'),
        'lvs': sig.get('lvs_errors'),
        'antenna': m.get('antenna__violating__nets'),
        'route': m.get('route__drc_errors'),
        'export_drc': (exp or {}).get('main', {}).get('violations'),
        'export_antenna': (exp or {}).get('antenna', {}).get('violations'),
        'export_xor': sig.get('gds_export', {}).get('xor_vs_librelane_gds'),
    }
    rtl_current = not ev['hardened_copy_missing'] and not ev['hardened_copy_differences']
    sdc_current = ev['sdc']['pnr'] is not None and ev['sdc']['pnr'] == ev['sdc']['signoff']
    clean = rtl_current and sdc_current and all(value == 0 for value in physical_checks.values())
    g = gls or {}
    hashes = g.get('source_hashes', {})
    current_gls = bool(hashes) and all((P/name).exists() and sha(P/name) == digest
                                     for name, digest in hashes.items())
    gls_pass = g.get('status') == 'pass' and current_gls and rtl_current
    reset = g.get('reset_safety', {})
    safe = gls_pass and reset.get('reset_snapshots', 0) >= 4 and reset.get('violations') == 0
    observable = gls_pass and g.get('observability', {}).get('mismatches') == []
    loopback = gls_pass and g.get('host_link_loopback', {}).get('status') == 'pass'
    def verdict(passed, evidence):
        return dict(proposal='pass' if passed else 'open', evidence=[evidence])
    area = m.get('design__die__area')
    state = m.get('design__instance__count__class:sequential_cell')
    return dict(
        timing=dict(
            method='OpenSTA on the recorded routed netlist and SPEF, using the specification clock periods.',
            per_corner=ft, measured_setup_targets_met=setup_met,
            measured_hold_targets_met=hold_met,
            envelope_note='Nominal tt is inside the accepted envelope. The listed broad ss/ff corners '
                          'do not replace qualification at 22–32 C and 3.15–3.35 V.'),
        tests=dict(
            digital=dict(
                safe=verdict(safe, 'evidence/digital-hardening-evidence.json#gate_level.reset_safety'),
                clean=verdict(clean, 'evidence/digital-hardening-evidence.json#signoff'),
                observable=verdict(observable, 'evidence/digital-hardening-evidence.json#gate_level.observability'),
                fallback=dict(proposal='waived_core')),
            hostio=dict(
                safe=dict(proposal='open', note='Assembled provider-pad safety remains a separate gate.'),
                clean=dict(proposal='open', note='Requires the assembled pad ring and full-chip checks.'),
                observable=verdict(loopback, 'evidence/digital-hardening-evidence.json#gate_level.host_link_loopback'),
                fallback=verdict(loopback, 'evidence/digital-hardening-evidence.json#gate_level.host_link_loopback'))),
        physical_check_counts=physical_checks,
        performance_vs_target=dict(
            per_corner=ft, area_um2=area, area_cap_um2=2500000,
            area_fits=None if area is None else area <= 2500000,
            sequential_cells=state, state_cap_bits=8192,
            state_fits=None if state is None else state <= 8192),
        hostio=dict(
            pad_toggle_screen=pads,
            target='156.25 MHz DDR pins, 312.5 Mword/s ten-bit host boundary',
            qualification='Routed timing, real pad/board timing, clock tolerance and bounded interruptions required.'),
        evidence_scope=dict(current_gls_sources=current_gls,
                            hardened_rtl_matches_current=rtl_current,
                            hardened_sdc_matches_current=sdc_current),
        open_risks=[
            'Target timing, state cap and footprint must pass on the final routed source snapshot.',
            'Accepted-envelope timing, real pads/board skew and full-chip assembly remain required.',
            'GLS is functional and has no SDF; physical timing requires STA.',
            'Observation wiring and fallbacks must be checked on the assembled physical chip.'])


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
                   klayout_export=rd('export/klayout-version.txt'), sta=(sta or {}).get('tool'), toolchain=load(out / 'toolchain.json')),
        pdk='gf180mcuD / gf180mcu_fd_sc_mcu7t5v0 in the recorded tool images',
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
            memory='Register-array FIFOs and capture/playback storage; counted inside the digital+memory allocation.',
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
    ev['hardened_copy_missing'] = sorted(
        f.name for f in (P / 'rtl').iterdir() if f.suffix in ('.sv', '.svh', '.vh')
        and not (out / 'design/rtl' / f.name).exists())
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
    Path(a.evidence).write_text(json.dumps(ev, indent=1) + '\n')
    print(json.dumps(dict(physical=ev['physical'], signoff=ev['signoff']), indent=1)[:4000])


if __name__ == '__main__':
    main()
