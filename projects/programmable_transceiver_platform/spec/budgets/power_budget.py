#!/usr/bin/env python3
"""Mode current, supply-drop and thermal budget for the operating envelope.

Spec-level budget owned by spec/power-partition.md. It reads the per-block
allocations in spec/analog-architecture.json, applies the branch overrides
exactly once, then substitutes evidence where evidence exists for the two
blocks that are still allocations (digital core, host IO). It writes
spec/budgets/power-budget.json and exits non-zero if --check finds a case
over its ceiling.

Envelope (MANDATE.md, tapeout-plan.md): Tj 22-32 C, die rail 3.15-3.35 V,
board source 3.3 V +-1 %. Wide-temperature corners do not gate performance.

Usage: python3 spec/budgets/power_budget.py [--check]
"""
import hashlib, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
AA = ROOT / 'spec/analog-architecture.json'
DH = ROOT / 'evidence/digital-hardening-evidence.json'
HOST_TYP = ROOT / 'evidence/host-power-allocation-screen.json'
HOST_ART = ROOT / 'evidence/artix-load-power-screen.json'
CLKPIN = ROOT / 'evidence/clock-power-screen.json'
ISL = ROOT / 'analog/island_support/evidence.json'
RFTX = ROOT / 'analog/rf_tx/generated/rf_tx-sim-ext.json'   # extracted rf_tx benches (rfdriver supply incl. board feed)
OUT = ROOT / 'spec/budgets/power-budget.json'

MODES = ['rf_rx', 'rf_tx', 'wired', 'usb', 'stopped']
# Board and package (tapeout-plan.md "Supply ring"); the bond values are the
# coordinator planning values, not measured.
V_SRC_MIN, V_SRC_MAX = 3.3 * 0.99, 3.3 * 1.01
V_DIE_MIN, V_DIE_MAX = 3.15, 3.35
R_BOND_EACH = 0.10            # ohm per bond (planning, ~2 mm 25 um Au)
N_SUPPLY, N_RETURN = 8, 10
SHARE_DERATE = 4.44           # unequal sharing: reproduces the plan's 25 mV @ 250 mA
R_BOARD = 0.020               # ohm, source sense point to COB pads (requirement on board, B2a)
R_GRID = 0.10                 # ohm, on-die ring + grid planning allocation (unextracted)
NATIVE_CELL_MA = 60           # GF180 IO supply cell DC capacity per cell
# Thermal: COB on FR4. No measured theta; range is a planning bound.
THETA_JA_COB = (40.0, 100.0)  # C/W, glob-top COB, still air, no heatsink (typical class, not measured)
TJ_WINDOW = (22.0, 32.0)
# Requirements this budget sets (spec/power-partition.md PWR-DIG-*, PWR-HOST-RF)
DIG_REQ_MA = {'rf': 40.0, 'wired_usb': 60.0}
HOST_RF_RATE_FACTOR = 0.5
T_CTRL_TOL = 2.0              # C, plate controller tolerance (requirement on board)

# RF direction recipe (PWR-08/PWR-09 design fix, RF-PWR-1 in scratch/reviews/interface-changes.md).
# Hardware already has the controls: adc EN = adc_*.config.enable AND state active (1.7 nA off,
# wakes on the next conversion; refbuf stays on); rfdriver/txmix/txsum en = state != off (reset
# 7.8 uA extracted); dac EN = enable AND state active. Wake of the gated rfdriver is measured
# (scratch/rf-pwr/exp_wake.json) and must stay inside the chip TDD switch budget (RF-154-TURN,
# <= 40 us). LNA/rxmix stay powered in TX (warm == on in hardware), so TX->RX keeps today's path.
RF_DIRECTION_OFF = {
    'rf_rx': ('rfdriver', 'txmix_i', 'txmix_q', 'txsum', 'dac_i', 'dac_q'),   # TX chain parked in RX
    'rf_tx': ('adc_i', 'adc_q'),                                             # ADCs disabled in TX
    'rf_duplex': (),                                                         # GX-3 TX+RX: all on
}
# Extracted block currents replace planning allocations in RF modes (rf_rx README, converters README).
RF_EVIDENCE_MA = {
    'lna': 11.7, 'rxmix_i': 1.9, 'rxmix_q': 1.9, 'rxfilter_i': 6.66, 'rxfilter_q': 6.66,
    'adc_i': 5.73, 'adc_q': 5.73, 'dac_i': 1.92, 'dac_q': 1.92,
}
# PWR-HOST-RF: RF recipe runs D2H at div2 (debug.host_link.rate, reg 0x51, hardware present). The
# chip's host-IO current is the D2H output drive; H2D pins are inputs.
RF_HOSTIO_FACTOR = 0.5


def rf_direction(case_name, mode):
    if case_name.startswith('rf_duplex'): return 'rf_duplex'
    return mode if mode in ('rf_rx', 'rf_tx') else None


def apply_rf_recipe(per, direction):
    """Return a copy of per-block currents with the RF direction recipe and evidence applied."""
    out = dict(per)
    for b, v in RF_EVIDENCE_MA.items():
        if b in out: out[b] = v
    for b in RF_DIRECTION_OFF[direction]:
        out[b] = 0.0
    if 'hostio' in out: out['hostio'] = round(out['hostio'] * RF_HOSTIO_FACTOR, 2)
    return out


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

def mode_totals(aa, override_branch=None):
    blocks = aa['blocks']; rp = aa['resource_policy']
    ov = rp['branch_current_overrides_ma'].get(override_branch, {}) if override_branch else {}
    applies = rp['branch_current_modes'].get(override_branch, []) if override_branch else []
    per = {m: {} for m in MODES}
    for n, b in blocks.items():
        cb = b.get('resource_allocation', {}).get('current_budget_ma', {})
        for m in MODES:
            v = cb.get(m, 0)
            if m in applies and n in ov: v = ov[n]
            per[m][n] = v
    return per

def main(check=False):
    aa = json.loads(AA.read_text()); dh = json.loads(DH.read_text())
    ceil = aa['resource_policy']['current_ceiling_ma']
    cases = {
        'rf_external_clock': ('external_rf_clock', 'rf_rx'),
        'rf_autonomous': (None, 'rf_rx'),
        'wired_onchip_pll': (None, 'wired'),
        'wired_external_clock': ('external_wired_clock', 'wired'),
        'wired_tmds': ('wired_tmds', 'wired'),
        'usb': (None, 'usb'),
        'stopped': (None, 'stopped'),
        # rf_tx cases (rfdriver at its extracted code-15 current, not the 28.92 mA allocation); duplex = the
        # rf_rx allocation (LNA on) with the driver also at its extracted current (GX-3 TX+RX).
        'rf_tx_external_clock': ('external_rf_clock', 'rf_tx'),
        'rf_tx_autonomous': (None, 'rf_tx'),
        'rf_duplex_external_clock': ('external_rf_clock', 'rf_rx'),
    }
    # ---- evidence for the two allocation-only blocks ----
    p_dig_w = dh['metrics_snapshot']['power__total']
    dig_vectorless_ma = p_dig_w / 3.3 * 1e3
    clk_pins = json.loads(CLKPIN.read_text())
    dig_clkpin_ma = max(sum(d['charging_current_ma'] for d in p['domains']) for p in clk_pins['profiles'])
    ht = json.loads(HOST_TYP.read_text()); ha = json.loads(HOST_ART.read_text())
    host_typ = max(sum(r['with_provisional_allowances_ma'] for r in ht['rows'] if r['case'] == c)
                   for c in {r['case'] for r in ht['rows']})
    host_8pf = sum(r['with_existing_allowances_ma'] for r in ha['rows'])
    evidence = {
        'digital': {
            'allocation_ma': {'rf': 19.5, 'wired_usb': 36.5},
            'lower_bound_ma': round(dig_clkpin_ma, 2),
            'lower_bound_basis': 'evidence/clock-power-screen.json: Liberty clock-pin charging only, older netlist; excludes tree, wires, internal, data',
            'upper_bound_ma': round(dig_vectorless_ma, 2),
            'upper_bound_basis': 'evidence/digital-hardening-evidence.json metrics_snapshot.power__total (FREEZE1, OpenROAD vectorless, nom_tt_025C_3v30, all SDC clocks at target, no mode gating, RTL 18/26 stale)',
            'budget_case_ma': round(dig_vectorless_ma, 2),
            'status': 'unverified: allocation is 5.7x below the only post-route power number',
        },
        'hostio': {
            'allocation_ma': 110,
            'typical_alternating_ma': round(host_typ, 2),
            'artix_8pf_alternating_ma': round(host_8pf, 2),
            'basis': 'evidence/host-power-allocation-screen.json, evidence/artix-load-power-screen.json (two-pad extrapolation + 25 % and 2 mA allowances; nominal; no SSO)',
            'budget_case_ma': round(host_8pf, 2),
            'status': 'marginal: 8 pF Artix load exceeds the 110 mA allocation by %.1f mA' % (host_8pf - 110),
        },
    }
    rt = json.loads(RFTX.read_text())['results']
    drv = []
    for k, v in rt.items():
        sm = (v.get('result') or {}).get('supply_mA')
        if isinstance(sm, dict): sm = sm.get('rfdriver')
        if isinstance(sm, (int, float)) and (k.startswith(('drv_', 'chain_', 'match_', 'corner_', 'mcorner_', 'scorner_', 'amam'))):
            drv.append((sm, k))
    drv_max, drv_case = max(drv)
    # coordinator 2026-11-12: the corner-sweep maximum (61.69 mA, ff/22/3.35 overdriven, scratch/rf-tx-d3/imax.json) is not in
    # rf_tx-sim-ext.json; the accepted allocation (61.7 mA) bounds it, so the budget uses the larger of the two
    _alloc = aa['blocks']['rfdriver']['resource_allocation']['current_budget_ma']['rf_tx']
    if _alloc > drv_max:
        drv_max, drv_case = _alloc, 'allocation (corner-sweep max 61.69 mA, scratch/rf-tx-d3/imax.json)'
    evidence['rfdriver'] = {
        'allocation_ma': aa['blocks']['rfdriver']['resource_allocation']['current_budget_ma']['rf_tx'],
        'budget_case_ma': round(drv_max, 2), 'worst_bench': drv_case,
        'basis': 'analog/rf_tx/generated/rf_tx-sim-ext.json: max rfdriver supply (island rail + board DC feed through the '
                 'RF_TX chokes) over every extracted code-15/linear/saturated/corner bench at the envelope',
        'status': 'evidence: allocation is %.1f mA low' % (drv_max - aa['blocks']['rfdriver']['resource_allocation']['current_budget_ma']['rf_tx']),
    }
    # ---- mode totals ----
    out_cases = {}
    for name, (branch, m) in cases.items():
        per = mode_totals(aa, branch)[m]
        rdir = rf_direction(name, m)
        if rdir:
            per = apply_rf_recipe(per, rdir)
            if rdir in ('rf_tx', 'rf_duplex'):      # rfdriver at its extracted code-15 current (set below)
                per['rfdriver'] = per.get('rfdriver', 0.0) or 0.0
        alloc = sum(per.values())
        ev = dict(per)
        if rdir in ('rf_tx', 'rf_duplex'):
            ev['rfdriver'] = evidence['rfdriver']['budget_case_ma']
        if m != 'stopped':
            ev['digital'] = evidence['digital']['budget_case_ma']
            ev['hostio'] = evidence['hostio']['budget_case_ma'] * (RF_HOSTIO_FACTOR if rdir else 1.0)
        ev_total = sum(ev.values())
        # target: digital re-hardened to the requirement PWR-DIG (<= 60 mA), host at evidence
        tgt = dict(ev)
        if m != 'stopped':
            rf = m.startswith('rf')
            tgt['digital'] = DIG_REQ_MA['rf' if rf else 'wired_usb']
            # RF payload (<= 0.96 Gb/s at 40 MS/s) fits the host link at div2
            # (1.44 Gb/s framed), so the RF mode runs the pins at half word rate.
            if rf: tgt['hostio'] = round(evidence['hostio']['budget_case_ma'] * HOST_RF_RATE_FACTOR, 2)   # same as ev now
        tgt_total = sum(tgt.values())
        c = ceil[m]
        if rdir in ('rf_tx', 'rf_duplex'):
            alloc = alloc - per['rfdriver'] + evidence['rfdriver']['budget_case_ma']   # measured, not allocated
        out_cases[name] = {
            'mode': m, 'branch_override': branch, 'ceiling_ma': c,
            'rf_direction_recipe': ({'direction': rdir, 'blocks_off': list(RF_DIRECTION_OFF[rdir]),
                                     'evidence_currents_ma': RF_EVIDENCE_MA, 'hostio_factor': RF_HOSTIO_FACTOR}
                                    if rdir else None),
            'allocation_ma': round(alloc, 2), 'allocation_margin_ma': round(c - alloc, 2),
            'evidence_bound_ma': round(ev_total, 2), 'evidence_margin_ma': round(c - ev_total, 2),
            'with_digital_requirement_ma': round(tgt_total, 2), 'with_digital_requirement_margin_ma': round(c - tgt_total, 2),
        }
    # ---- supply drop at the worst current of each case set ----
    r_bond = R_BOND_EACH * (1 / N_SUPPLY + 1 / N_RETURN) * SHARE_DERATE
    isl = json.loads(ISL.read_text())['island_switch']
    island = {}
    alloc_w = mode_totals(aa)['wired']
    for k, v in isl.items():
        if not isinstance(v, dict) or 'drop' not in v: continue
        rc = v['drop']['extracted_full_rc_functional_max_v']; dc = v['design_current_ma']
        peak = v.get('peak_allocation_ma', dc)
        island[k] = {'design_current_ma': dc, 'peak_allocation_ma': peak,
                     'drop_at_design_mv': round(rc * 1e3, 2), 'drop_at_peak_mv': round(rc * peak / dc * 1e3, 2),
                     'margin_to_20mv_at_peak_mv': round(20 - rc * peak / dc * 1e3, 2)}
    worst_island_mv = max(i['drop_at_design_mv'] for i in island.values())
    drop = {}
    for label, key in (('allocation', 'allocation_ma'), ('evidence_bound', 'evidence_bound_ma'),
                       ('with_digital_requirement', 'with_digital_requirement_ma')):
        i_max = max(c[key] for c in out_cases.values()) / 1e3
        d_board = R_BOARD * i_max * 1e3; d_bond = r_bond * i_max * 1e3; d_grid = R_GRID * i_max * 1e3
        total = d_board + d_bond + d_grid + worst_island_mv
        avail = (V_SRC_MIN - V_DIE_MIN) * 1e3
        drop[label] = {'i_max_ma': round(i_max * 1e3, 2), 'board_mv': round(d_board, 1), 'bond_mv': round(d_bond, 1),
                       'grid_mv': round(d_grid, 1), 'island_switch_mv': round(worst_island_mv, 1),
                       'total_mv': round(total, 1), 'available_mv': round(avail, 1), 'margin_mv': round(avail - total, 1),
                       'supply_cells_needed_at_60ma': math.ceil(i_max * 1e3 / NATIVE_CELL_MA),
                       'supply_cells_available': N_SUPPLY,
                       'cell_utilization_even_share': round(i_max * 1e3 / (NATIVE_CELL_MA * N_SUPPLY), 3)}
    # ---- thermal ----
    tmds_die_mw = 2.8 * 10 + 3.3 * 5.1   # driver leg sinking 10 mA at ~2.8 V + ff clamp leak on idle leg
    ext_mw = 6.48                        # resource_policy.external_pad_dissipation (RX level divider)
    thermal = {}
    for label, key in (('allocation', 'allocation_ma'), ('evidence_bound', 'evidence_bound_ma'),
                       ('with_digital_requirement', 'with_digital_requirement_ma')):
        p_w = max(c[key] for c in out_cases.values()) * V_DIE_MAX / 1e3 + (tmds_die_mw + ext_mw) / 1e3
        p_min = out_cases['stopped'][key] * V_DIE_MIN / 1e3
        span = TJ_WINDOW[1] - TJ_WINDOW[0] - T_CTRL_TOL
        thermal[label] = {'p_max_w': round(p_w, 3), 'p_stopped_w': round(p_min, 3),
                          'free_air_rise_c': [round(t * p_w, 1) for t in THETA_JA_COB],
                          'required_theta_junction_to_controlled_plate_c_per_w': round(span / (p_w - p_min), 2),
                          'note': 'Tj window 10 C minus 2 C control tolerance must absorb the full stopped-to-max power step (mode switches are faster than any plate loop).'}
    res = {
        'generated_by': 'spec/budgets/power_budget.py',
        'inputs': {str(p.relative_to(ROOT)): sha(p) for p in (AA, DH, HOST_TYP, HOST_ART, CLKPIN, ISL, RFTX)},
        'envelope': {'tj_c': TJ_WINDOW, 'v_die': [V_DIE_MIN, V_DIE_MAX], 'v_source': [round(V_SRC_MIN, 3), round(V_SRC_MAX, 3)]},
        'assumptions': {'r_bond_each_ohm': R_BOND_EACH, 'supply_bonds': N_SUPPLY, 'return_bonds': N_RETURN,
                        'unequal_share_derate': SHARE_DERATE, 'r_bond_effective_ohm': round(r_bond, 4),
                        'r_board_ohm': R_BOARD, 'r_grid_ohm_allocation': R_GRID,
                        'theta_ja_cob_c_per_w_range': THETA_JA_COB, 'tmds_die_dissipation_mw': round(tmds_die_mw, 1)},
        'reconciliation': {
            'architecture_resource_totals': aa['resource_totals']['current_ma'],
            'readiness_current_envelope_ma_superseded': {'rf_external_clock': 236.27, 'rf_autonomous': 244.55, 'wired': 260.96, 'usb': 247.39,
                'note': 'Not reproducible from analog-architecture.json or any recorded derivation (wired/usb are +16.14 mA, RF external +12.18, autonomous -8.47 vs the per-block sum). Superseded by this script.'},
        },
        'evidence_substitutions': evidence,
        'cases': out_cases, 'island_switch': island, 'supply_drop': drop, 'thermal': thermal,
    }
    OUT.write_text(json.dumps(res, indent=1) + '\n')
    fails = [n for n, c in out_cases.items() if c['allocation_margin_ma'] < 0 and n not in ('rf_autonomous', 'rf_tx_autonomous')]
    print(json.dumps({k: {kk: c[kk] for kk in ('ceiling_ma', 'allocation_ma', 'evidence_bound_ma', 'with_digital_requirement_ma')} for k, c in out_cases.items()}, indent=1))
    print(json.dumps(drop, indent=1)); print(json.dumps(thermal, indent=1))
    if check:
        ev_fail = [n for n, c in out_cases.items() if c['with_digital_requirement_margin_ma'] < 0 and n not in ('rf_autonomous', 'rf_tx_autonomous')]
        if fails or ev_fail or drop['with_digital_requirement']['margin_mv'] < 0:
            print('CHECK FAIL', fails, ev_fail); return 1
    return 0

if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
