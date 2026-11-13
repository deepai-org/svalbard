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
    # RF RX owner 2026-11-13 (uncommitted, see interface-changes RC-16u): LNA allocation 18.9 RX / 11.7 with lna.bias.lo; these are
    # LIMITS (characterize.py checks <= 19.0 / 11.8), not measurements: the bonded-source candidate measured 19.37 / 11.90 tt and
    # is withdrawn; the on-chip-degeneration stage is to be measured against them (screen: 17.6-18.3 mA).
    'lna': 18.9, 'rxmix_i': 3.01,
    'rxmix_q': 3.01,   # fork V TIA (1.2 mA tail per OTA, no hib pin): extracted tt 3.01-3.02, corners 2.80-3.09
    'rxfilter_i': 5.22, 'rxfilter_q': 5.22,   # FD bbfilter (FS-1/FS-2, committed ca80067; corners 4.95-5.32)
    'adc_i': 5.73, 'adc_q': 5.73, 'dac_i': 1.92, 'dac_q': 1.92,
}
# PWR-HOST-RF: RF recipe runs D2H at div2 (debug.host_link.rate, reg 0x51, hardware present). The
# chip's host-IO current is the D2H output drive; H2D pins are inputs.
RF_HOSTIO_FACTOR = 0.5
LNA_DUPLEX_MA = 11.7   # RC-16k reduced-bias LNA state (lobias = 1), allocation


def rf_direction(case_name, mode):
    if case_name.startswith('rf_duplex'): return 'rf_duplex'
    return mode if mode in ('rf_rx', 'rf_tx') else None


def apply_rf_recipe(per, direction):
    """Return a copy of per-block currents with the RF direction recipe and evidence applied."""
    out = dict(per)
    for b, v in RF_EVIDENCE_MA.items():
        if b in out: out[b] = v
    if direction in ('rf_tx', 'rf_duplex') and 'lna' in out:   # RC-16k rule: lna.bias.lo = 1 (and rxmix hib = 0) whenever the TX chain is on
        out['lna'] = LNA_DUPLEX_MA       # RC-16k: validator forces lna.bias.lo whenever TX is on
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
    res['pd2_reconciliation'] = pd2_reconcile(aa)   # PD2: measured-evidence reconciliation, island partition, restated ceilings
    OUT.write_text(json.dumps(res, indent=1) + '\n')
    fails = [n for n, c in out_cases.items() if c['allocation_margin_ma'] < 0 and n not in ('rf_autonomous', 'rf_tx_autonomous')]
    print(json.dumps({k: {kk: c[kk] for kk in ('ceiling_ma', 'allocation_ma', 'evidence_bound_ma', 'with_digital_requirement_ma')} for k, c in out_cases.items()}, indent=1))
    print(json.dumps(drop, indent=1)); print(json.dumps(thermal, indent=1))
    if check:
        ev_fail = [n for n, c in out_cases.items() if c['with_digital_requirement_margin_ma'] < 0 and n not in ('rf_autonomous', 'rf_tx_autonomous')]
        if fails or ev_fail or drop['with_digital_requirement']['margin_mv'] < 0:
            print('CHECK FAIL', fails, ev_fail); return 1
    return 0


# =====================================================================================================================
# PD2 (power-delivery owner, 2026-11-13): reconciliation of the budget against every block's CURRENT evidence, the
# island partition and the restated ceilings. Additive: nothing above this line is changed by it (the m1 PDN model and
# the RF RX owner's --check use the functions above). Table and decisions: spec/power-delivery.md sections 1-2.
# Each row: (block, island, {case-group: (nominal tt/27/3.3 mA, worst in-envelope mA)}, budget blocks it is compared
# with, view, source). Views: ext = extracted, sch = schematic, est = estimate (no bench), lim = owner's limit.
# Case groups: W wired 2.5 Gb/s on-chip PLL (ring 625 MHz), U USB HS, T TMDS TX-only, RXe/RXa RF RX with external /
# autonomous LO, TXe/TXa RF TX, DXe/DXa duplex (GX-3). RF = all six RF cases, A = the three autonomous-LO cases.
PD2_CASES = ['W', 'U', 'T', 'RXe', 'RXa', 'TXe', 'TXa', 'DXe', 'DXa', 'stopped']
PD2_GROUP = {'RF': ('RXe', 'RXa', 'TXe', 'TXa', 'DXe', 'DXa'), 'A': ('RXa', 'TXa', 'DXa'), 'RX': ('RXe', 'RXa'),
             'TX': ('TXe', 'TXa'), 'DX': ('DXe', 'DXa'), 'TD': ('TXe', 'TXa', 'DXe', 'DXa'), 'RD': ('RXe', 'RXa', 'DXe', 'DXa'),
             'WU': ('W', 'U'), 'WUT': ('W', 'U', 'T'), 'ACT': ('W', 'U', 'T', 'RXe', 'RXa', 'TXe', 'TXa', 'DXe', 'DXa')}
PD2_BUDGET_MODE = {'W': 'wired', 'U': 'usb', 'T': 'wired', 'RXe': 'rf_rx', 'RXa': 'rf_rx', 'TXe': 'rf_tx', 'TXa': 'rf_tx',
                   'DXe': 'rf_rx', 'DXa': 'rf_rx', 'stopped': 'stopped'}
RFDRV_DIE_FRACTION = 0.393   # rf_tx-sim-ext.json safe_en_lo_stopped: rfdriver_rail 22.85 mA of 58.15 (board feed through the
                             # RF_TX chokes 35.30). Only the output-pair tail goes through the pads (circuits.py:rfdriver).
MEASURED = [
 # ---- rf_rx island
 ('lna', 'rf_rx', {'RX': (18.9, 21.4), 'TD': (11.7, 13.4)}, ('lna',), 'lim',
  'limit 18.9 / 11.7 (RC-16u, characterize.py); withdrawn candidate 19.37 / 11.90 tt, 21.40 / 13.43 ff/22/3.35 (scratch/rf-lna-p/v8/idd.log); the stage to be built is not measured'),
 ('rxmix_i', 'rf_rx', {'RF': (3.01, 3.09)}, ('rxmix_i',), 'ext', 'analog/rf_rx/generated/rxmix_i-evidence.json extracted_nominal.idd_a (fork V)'),
 ('rxmix_q', 'rf_rx', {'RF': (3.01, 3.09)}, ('rxmix_q',), 'ext', 'same, rxmix_q'),
 ('bbfilter_i', 'rf_rx', {'RF': (5.22, 5.32)}, ('rxfilter_i',), 'ext', 'analog/rf_rx/generated/bbfilter_i-evidence.json extracted_nominal.idd_a'),
 ('bbfilter_q', 'rf_rx', {'RF': (5.22, 5.32)}, ('rxfilter_q',), 'ext', 'same, bbfilter_q'),
 # ---- rf_tx island
 ('txsum', 'rf_tx', {'TD': (2.01, 2.03)}, ('txsum', 'txmix_i', 'txmix_q'), 'ext', 'rf_tx-sim-ext.json chain_dc supply_mA.txsum (carries both txmix tails)'),
 ('rfdriver', 'rf_tx', {'TD': (58.4, 61.7)}, ('rfdriver',), 'ext',
  'rf_tx-sim-ext.json chain_zero 58.40, scratch/rf-tx-d3/imax.json 61.694 ff/22/3.35 overdriven; TOTAL incl. the board feed: '
  'die rail = 0.393 x total (22.9 / 24.3 mA), board feed through the RF_TX pads = 0.607 x total, returning through die VSS'),
 # ---- conv island
 ('adc_i', 'conv', {'RD': (5.73, 6.3)}, ('adc_i',), 'ext', 'converters/generated/adc_i-evidence.json 5.731 at 40 MS/s; no corner current recorded: worst = 1.1 x (assumed)'),
 ('adc_q', 'conv', {'RD': (5.72, 6.3)}, ('adc_q',), 'ext', 'adc_q-evidence.json 5.721; worst assumed 1.1 x'),
 ('dac_i', 'conv', {'TD': (2.07, 2.28)}, ('dac_i',), 'ext', 'dac_i-evidence.json 2.069; worst assumed 1.1 x'),
 ('dac_q', 'conv', {'TD': (2.07, 2.28)}, ('dac_q',), 'ext', 'dac_q-evidence.json; worst assumed 1.1 x'),
 ('refbuf', 'conv', {'RF': (1.56, 1.56)}, ('refbuf',), 'ext', 'refbuf-evidence.json quiescent 0.553 (0.556 ff) + 1.0 mA delivered-reference allowance'),
 # ---- lo island (VDD_LO: regulated QVCO rail) and lod island (VDD_LOD)
 ('qvco', 'lo', {'A': (23.5, 25.0)}, ('rfpll',), 'ext', 'scratch/lo/r5_pn/ext12.json i_vdd_ma 22.11-25.01 over four tank cases (no tt/27 run of r6b)'),
 ('lo_pfdcp', 'lo', {'A': (1.0, 1.5)}, (), 'est', 'LO-INTEGRATION.md section 3: order 1 mA, not measured'),
 ('lo_vreg', 'lo', {'A': (0.5, 1.0)}, (), 'est', 'VDD_LO regulator quiescent: allowance (PD2-11), no design yet'),
 ('lo_mmd', 'lod', {'A': (26.3, 34.8)}, (), 'ext', 'scratch/lo/r4_loop/f/mmdxA.json, mmdxB.json idd_ma at 3.1 GHz: tt 25.8-26.3, ff/22/3.35 34.76, ss 18.8-19.3 (24.3-25.1 tt at 2.4-2.45 GHz in the logs)'),
 ('qvco_pre', 'lod', {'A': (3.0, 4.0)}, (), 'est', 'LO-INTEGRATION.md section 3: lo_qvco.VDDB PRE buffer, "a few mA" of 2.4 GHz CMOS current, not measured'),
 ('lo_mmd_qdum', 'lod', {'A': (8.0, 10.0)}, (), 'est', 'LO-INTEGRATION.md: ~8 mA by design (two 2.6 mA latches + followers), not measured'),
 ('lo_ext', 'lod', {'RF': (11.3, 13.74)}, ('quadrature',), 'ext',
  'scratch/timing/lo_ext/results.json internal 11.05 / 13.65; scratch/lo/r4_lo11/results.json external via the CML driver 11.2-11.3 / 13.74 (published lo_ext-evidence.json 16.02 is stale)'),
 # ---- pll island (ring PLLs behind pt_pll_vreg2, clock mux / word clock, reference receiver)
 ('pll_cdr', 'pll', {'WU': (6.94, 10.2), 'RF': (6.85, 10.2)}, ('cdr',), 'ext',
  'timing/generated/pll_ring-evidence.json i_on_ma 6.94 at 625 MHz, host_follow 6.85; no corners on the r9v cell: worst = older supply sweep 10.2 (pll_vreg/evidence/pll_ring-f-vs-supply.json)'),
 ('pll_tx', 'pll', {'W': (6.94, 10.2), 'U': (6.94, 10.2), 'T': (5.0, 8.0)}, ('rfpll',), 'est', 'pt_pll_ring_core has NO current evidence: taken equal to pll_cdr'),
 ('pll_misc', 'pll', {'WU': (1.0, 2.0)}, (), 'est', 'pt_cdr analog cell + pt_pll_vreg2 quiescent: not in any evidence file'),
 ('clockmux', 'pll', {'WUT': (1.35, 1.55), 'RF': (0.32, 0.40)}, ('clockmux',), 'ext', 'timing/generated/clockmux-evidence.json (9.67 mA budget is not in the current file)'),
 ('wordclk', 'pll', {'WUT': (2.30, 2.42), 'RF': (1.36, 2.42)}, ('clocktree',), 'ext', 'timing/generated/wordclk-evidence.json 1.18-2.30, 2.42 ff/32/3.35 (no clocktree evidence exists)'),
 ('rx_ref_in', None, {'WUT': (3.49, 4.63), 'A': (3.49, 4.63)}, ('refinput',), 'ext',
  'timing/generated/diff_clk_rx-evidence.json 3.49 at 100 MHz, 4.63 ff/32/3.35; on the always-on core rail at the REF pad (LO-INTEGRATION.md), not on the pll island; off in the external-LO cases (REF_IN carries the LO)'),
 ('prescale', 'pll', {'RF': (1.99, 2.40)}, (), 'ext', 'timing/generated/prescale-evidence.json 1.99 at 2.5 GHz /16, tt only: worst assumed 1.2 x'),
 # ---- wired_rx island
 ('ctle', 'wired_rx', {'W': (4.91, 5.31)}, ('ctle',), 'ext', 'wired_rx/generated/ctle-evidence.json'),
 ('slicer', 'wired_rx', {'W': (7.25, 9.8), 'U': (6.33, 7.5)}, ('slicer',), 'ext', 'slicer-evidence.json iavg 7.25 at 625 quarter, 6.33 USB HS; worst = 32.2 mW at 810 quarter; USB worst assumed'),
 ('detect', 'wired_rx', {'WU': (2.31, 2.38)}, ('detect',), 'ext', 'detect-evidence.json'),
 ('termination', 'wired_rx', {'WU': (1.25, 1.56)}, ('termination',), 'ext', 'termination-evidence.json idd_div'),
 ('rxlevel', 'wired_rx', {'W': (0.03, 0.04)}, ('rxlevel',), 'ext', 'rxlevel-evidence.json'),
 ('rxselect', 'wired_rx', {'WU': (2.0, 2.0)}, ('rxselect',), 'est', 'no active current in rxselect-evidence.json: the 2 mA allocation is kept'),
 ('vthdac', 'wired_rx', {'WU': (0.53, 0.70)}, (), 'ext', 'vthdac-evidence.json extracted i_uA'),
 ('ctle_follower', 'wired_rx', {'W': (6.3, 6.9)}, (), 'est',
  'MW-13-FIX (interface-changes.md): proposed CTLE r4 source followers, 3 mA/side + 0.3 mA bias; not implemented, awaiting approval; worst assumed 1.1 x'),
 # ---- wired_cap island (capture and its phase trim)
 ('ptrim', 'wired_cap', {'W': (18.0, 21.0), 'U': (13.8, 16.1)}, (), 'est',
  'MW-14-FIX (interface-changes.md): pt_ptrim redesign in progress, 18-21 mA for 8 channels at 625 MHz; published cell not functional; USB scaled by 480/625'),
 ('wrx_cap', 'wired_cap', {'W': (44.78, 46.64), 'U': (34.87, 36.5)}, (), 'ext',
  'staged r7 scratch/wired_rx/r7cap/stage/results.json 44.78 at 625 MHz (45.15 ff), 34.87 at 480; worst = published r5h wrx_cap-evidence.json ext_q625 46.64 (corner not recorded; schematic 19.78); USB worst assumed 1.05 x'),
 # ---- wired_tx island
 ('wiredtx', 'wired_tx', {'W': (35.3, 37.46), 'T': (29.9, 32.0)}, ('wiredtx',), 'ext',
  'scratch/wired_tx/sim-results.json cornerq2.5 33.21 ss - 37.46 ff/22/3.35 (no tt run: nominal = mid), int_tmds_q1g485 29.90'),
 ('usbhs', 'wired_tx', {'U': (18.2, 20.0)}, ('usbhs',), 'ext', 'analog/pads/README.md 16.9-18.2 mA after trim; worst assumed 1.1 x'),
 # ---- raw ring (never switched)
 ('bias', None, {'ACT': (0.40, 0.52), 'stopped': (0.40, 0.52)}, ('bias', 'monitor'), 'sch', 'core_support/README.md 0.30-0.52 over the function window'),
 ('aosc', None, {'ACT': (0.376, 0.484), 'stopped': (0.376, 0.484)}, ('aosc',), 'ext', 'timing/generated/aosc-evidence.json i_on_ma (register reset = enabled)'),
 ('usbfs', None, {'U': (8.0, 8.0)}, ('usbfs',), 'est', 'allocation (provider pad drivers), no bench'),
]
# Debug island: on only while observing; not in the mode sums. All on at once = 51 / 56 mA against the 40 mA switch.
DEBUG_MEASURED = [('bb_tap x3', 3.04, 3.09, 'bb_tap-evidence.json'), ('clk_obs x2', 9.92, 10.28, 'clk_obs-evidence.json'),
                  ('ring_osc', 0.42, 0.53, 'ring_osc-evidence.json'), ('vco_replica', 9.28, 11.78, 'vco_replica-evidence.json (VCTRL 3.3 V)'),
                  ('rx_aux_clk / rx_wclk_in / rx_wtx_ext', 15.3, 15.3, 'diff_clk_rx-evidence.json 5.10 each at 1 GHz'),
                  ('lo_obs', 6.62, 8.03, 'scratch/timing/lo_obs/results.json'), ('char structures', 6.49, 6.49, 'characterization/README.md')]
# Digital macro and host IO (allocation-only blocks): nominal = newest routed run, worst = evidence bound, req = PWR-DIG.
DIG_MEAS = {'nominal': 72.09, 'worst': 81.79, 'req_wired_usb': DIG_REQ_MA['wired_usb'], 'req_rf': DIG_REQ_MA['rf'],
            'src': 'AC1_R4 post-route vectorless 0.23791 W (scratch/digital-hardening-ac1-r4 .../power.rpt); CLOSE_R2 0.26992 W (evidence/digital-hardening-evidence.json)'}
HOST_MEAS = {'nominal': 95.24, 'worst': 116.82, 'src': 'evidence/host-power-allocation-screen.json / artix-load-power-screen.json (x 0.5 in RF modes, PWR-HOST-RF)'}
# Island partition (PD2-1) and the switch master each island instantiates. The masters are the five verified cells
# (analog/island_support, design current / full-RC worst-corner on-resistance from evidence.json).
SWITCH_MASTER = {'isw_wired': (80, 0.2484, 0.0641), 'isw_pll': (60, 0.2877, 0.0530), 'isw_rf': (55, 0.3007, 0.0500),
                 'isw_debug': (40, 0.3878, 0.0370), 'isw_conv': (30, 0.4807, 0.0320)}   # (mA, ohm, mm2)
ISLAND_SWITCH = {'wired_rx': 'isw_debug', 'wired_cap': 'isw_wired', 'wired_tx': 'isw_debug', 'rf_rx': 'isw_rf', 'rf_tx': 'isw_debug', 'lod': 'isw_wired',
                 'lo': 'isw_conv', 'pll': 'isw_debug', 'conv': 'isw_conv', 'debug': 'isw_debug'}
# Loads that are on only for debug but sit on a functional island rail: counted for the switch, not in the mode sums.
ISLAND_EXTRA_WORST_MA = {'lod': 8.03}   # lo_obs (VDD_LOD, LO-INTEGRATION.md), scratch/timing/lo_obs/results.json ff/22/3.35
SWITCH_DROP_LIMIT_MV = 20.0
# Switch design current of an island = sum of the worst in-envelope currents, with 1.25 x on every contribution that
# is not a measurement of the cell that will be built (views est and lim, and the rfdriver die-rail share, which comes
# from one bench). The drop limit and the master's design current are both checked at that current.
EST_MARGIN = 1.25
# Restated ceilings (mA, total chip current incl. the rfdriver board feed), worst in-envelope analog + digital at PWR-DIG.
PD2_CEILING_MA = {'wired_usb': 360, 'rf_external_lo': 260, 'rf_autonomous_lo': 340}   # >= 4 % over the worst case of each group


def pd2_expand(row):
    out = {}
    for g, v in row[2].items():
        for c in PD2_GROUP.get(g, (g,)): out[c] = v
    return out


def pd2_reconcile(aa=None):
    """Per-case and per-island sums. dig: 'req' = PWR-DIG requirement, 'meas' = nominal 72.09 / worst 81.79."""
    aa = aa or json.loads(AA.read_text())
    res = {'cases': {}, 'islands': {}, 'rows': []}
    for c in PD2_CASES:
        rf = c not in ('W', 'U', 'T', 'stopped'); hf = RF_HOSTIO_FACTOR if rf else 1.0
        isl = {}; nom = worst = 0.0
        for r in MEASURED:
            v = pd2_expand(r).get(c)
            if not v: continue
            nom += v[0]; worst += v[1]
            if r[1]:
                f = RFDRV_DIE_FRACTION if r[0] == 'rfdriver' else 1.0
                k = EST_MARGIN if (r[4] in ('est', 'lim') or r[0] == 'rfdriver') else 1.0
                a = isl.setdefault(r[1], [0.0, 0.0, 0.0]); a[0] += v[0]*f; a[1] += v[1]*f; a[2] += v[1]*f*k
        if c == 'stopped':
            dig = (2.0, 2.0, 2.0); host = (1.0, 1.0)
        else:
            dig = (DIG_MEAS['req_rf' if rf else 'req_wired_usb'], DIG_MEAS['nominal'], DIG_MEAS['worst'])
            host = (HOST_MEAS['nominal']*hf, HOST_MEAS['worst']*hf)
        board = sum(pd2_expand(r).get(c, (0, 0))[1] for r in MEASURED if r[0] == 'rfdriver')*(1-RFDRV_DIE_FRACTION)
        ceil = PD2_CEILING_MA['wired_usb' if not rf else 'rf_autonomous_lo' if c.endswith('a') else 'rf_external_lo']
        res['cases'][c] = {
            'analog_nominal_ma': round(nom, 2), 'analog_worst_ma': round(worst, 2),
            'total_nominal_dig_meas_ma': round(nom+dig[1]+host[0], 2), 'total_worst_dig_meas_ma': round(worst+dig[2]+host[1], 2),
            'total_worst_dig_req_ma': round(worst+dig[0]+host[1], 2), 'rfdriver_board_feed_worst_ma': round(board, 2),
            'through_die_supply_bonds_worst_dig_req_ma': round(worst+dig[0]+host[1]-board, 2),
            'old_ceiling_ma': aa['resource_policy']['current_ceiling_ma'][PD2_BUDGET_MODE[c]], 'pd2_ceiling_ma': ceil,
            'margin_to_pd2_ceiling_ma': round(ceil-(worst+dig[0]+host[1]), 2),
            'margin_to_pd2_ceiling_dig_meas_ma': round(ceil-(worst+dig[2]+host[1]), 2),
            'islands_nominal_worst_design_ma': {k: [round(x, 2) for x in v] for k, v in isl.items()}}
        for k, v in isl.items():
            a = res['islands'].setdefault(k, {'worst_ma': 0.0, 'design_ma': 0.0, 'case': None})
            if v[2] > a['design_ma']: a.update(worst_ma=round(v[1], 2), design_ma=round(v[2], 2), case=c)
    res['islands']['debug'] = {'worst_ma': 40.0, 'design_ma': 40.0, 'case': 'debug rule: at most 40 mA of debug loads enabled at once (all on = %.0f / %.0f mA)'
                               % (sum(d[1] for d in DEBUG_MEASURED), sum(d[2] for d in DEBUG_MEASURED))}
    for k, a in res['islands'].items():
        a['worst_ma'] = round(a['worst_ma']+ISLAND_EXTRA_WORST_MA.get(k, 0.0), 2)
        a['design_ma'] = round(a['design_ma']+ISLAND_EXTRA_WORST_MA.get(k, 0.0), 2)
        m = ISLAND_SWITCH[k]; des, ron, area = SWITCH_MASTER[m]
        a.update(switch_master=m, master_design_ma=des, ron_full_rc_worst_ohm=ron, area_mm2=area,
                 drop_at_worst_mv=round(ron*a['worst_ma'], 2), drop_at_design_mv=round(ron*a['design_ma'], 2),
                 drop_limit_mv=SWITCH_DROP_LIMIT_MV,
                 ok=bool(ron*a['design_ma'] <= SWITCH_DROP_LIMIT_MV and a['design_ma'] <= des))
    res['switch_area_mm2'] = round(sum(a['area_mm2'] for a in res['islands'].values()), 4)
    blocks = aa['blocks']
    for r in MEASURED:
        ex = pd2_expand(r); c = max(ex, key=lambda k: ex[k][1])
        bud = sum(blocks[b]['resource_allocation']['current_budget_ma'].get(PD2_BUDGET_MODE[c], 0) for b in r[3]) if r[3] else None
        res['rows'].append({'block': r[0], 'island': r[1] or 'raw ring', 'case': c, 'budget_ma': bud, 'budget_blocks': list(r[3]),
                            'measured_nominal_ma': ex[c][0], 'measured_worst_ma': ex[c][1], 'view': r[4], 'source': r[5]})
    return res


def pd2_markdown(res):
    L = ['| Block | Island | Case | Budget (mA) | Measured nominal | Worst in-envelope | View | Source |', '| --- | --- | --- | ---: | ---: | ---: | --- | --- |']
    for r in res['rows']:
        b = 'none' if r['budget_ma'] is None else ('%.2f' % r['budget_ma'])
        L.append(f"| {r['block']} | {r['island']} | {r['case']} | {b} | {r['measured_nominal_ma']:.2f} | {r['measured_worst_ma']:.2f} | {r['view']} | {r['source']} |")
    L += ['', '| Case | Analog nominal | Analog worst | Total nominal (digital 72.1) | Total worst (digital 81.8) | Total worst, digital at PWR-DIG | of which board feed | Old ceiling | New ceiling | Margin at PWR-DIG | Margin at 81.8 mA |',
          '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c, v in res['cases'].items():
        L.append(f"| {c} | {v['analog_nominal_ma']:.1f} | {v['analog_worst_ma']:.1f} | {v['total_nominal_dig_meas_ma']:.1f} | {v['total_worst_dig_meas_ma']:.1f} | "
                 f"{v['total_worst_dig_req_ma']:.1f} | {v['rfdriver_board_feed_worst_ma']:.1f} | {v['old_ceiling_ma']} | {v['pd2_ceiling_ma']} | {v['margin_to_pd2_ceiling_ma']:+.1f} | {v['margin_to_pd2_ceiling_dig_meas_ma']:+.1f} |")
    L += ['', '| Island | Worst current (mA) | Design current, 1.25 x on estimates (mA) | Case | Switch master | Master design (mA) | Drop at worst (mV) | Drop at design (mV) | Area (mm2) |',
          '| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |']
    for k, a in res['islands'].items():
        L.append(f"| {k} | {a['worst_ma']:.1f} | {a['design_ma']:.1f} | {a['case']} | {a['switch_master']} | {a['master_design_ma']} | {a['drop_at_worst_mv']:.1f} | {a['drop_at_design_mv']:.1f} | {a['area_mm2']:.4f} |")
    return '\n'.join(L)


if __name__ == '__main__':
    if '--reconcile' in sys.argv:      # PD2: print the reconciliation tables (markdown) and exit; writes nothing
        _r = pd2_reconcile(); print(pd2_markdown(_r))
        _bad = [k for k, a in _r['islands'].items() if not a['ok']] + [c for c, v in _r['cases'].items() if v['margin_to_pd2_ceiling_ma'] < 0]
        _ev = [c for c, v in _r['cases'].items() if v['margin_to_pd2_ceiling_dig_meas_ma'] < 0]
        print('\nPD2 CHECK', 'FAIL ' + str(_bad) if _bad else 'PASS (islands at their design current; ceilings with the digital macro at PWR-DIG)')
        print('over the ceiling with the digital macro at its measured 81.8 mA (PWR-DIG not yet met):', _ev or 'none'); sys.exit(1 if _bad else 0)
    sys.exit(main('--check' in sys.argv))
