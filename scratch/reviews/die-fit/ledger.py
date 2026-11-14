#!/usr/bin/env python3
"""Die-fit study (2026-11-14): honest demand ledger. Every instance of integration/top/pt_chip.conn plus every booked
(never-built / reserve) item, with core area in three columns: published today / staged candidate / target.
Plain CSV + markdown + json out. Read-only on design files.   python3 ledger.py"""
import sys, re, csv, json, collections, os
R = '/home/ubuntu/svalbard'; P = f'{R}/projects/programmable_transceiver_platform'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f'{P}/integration/top')
import check_top
inst, ports, waive, err = check_top.parse(open(f'{P}/integration/top/pt_chip.conn').read())
assert not err
import subprocess
CONN_REV = subprocess.run(['git','-C',R,'log','-1','--format=%h','--',f'{P}/integration/top/pt_chip.conn'],capture_output=True,text=True).stdout.strip()
CORE_MM2 = 3028.0*4218.0/1e6     # 452..3480 x 452..4670 (report-v6 core_um)

U = 'scratch/area-pass-4/util.json'; AB = 'scratch/chip-assembly-v5/run2/abstracts.json'
MS = 'scratch/reviews/die-fit/m45free_staged.json (staged GDS bbox)'
# master: (published um2, staged um2, target um2, confidence H/M/L, source, flags/note)   None = same as the column to its left
M = {
 # ---- digital, always-on ------------------------------------------------------------------------------------
 'pt_digital_macro': (2814000, None, None, 'H', 'digital NOTES TC7/TC8: 1716 x 1640', 'must not shrink (AP4-8 2.45 not reachable); absorbs decode glue, 129 iso AND2, LO/CDR/USB control, decap row cells: cells 1.764 mm2 = 67.4 %'),
 'por': (9469, None, None, 'H', AB, ''), 'pt_aosc': (12864, None, None, 'H', U, ''),
 'pt_core_bias': (301799, None, 180000, 'M', AB+'; target area-pass-4 s1 (lever 13, not started)', 'v5 abstract outline, util 0.24'),
 'pt_bias_ext': (4436, None, None, 'M', 'two pt_bias_tap2 cells of 2,218 (scratch/pads-core/bias/pub, review R10)', 'staged, not published (D-BIAS); in no floorplan'),
 # ten islands (conn commit 4790054, power-delivery.md s2): 5 x isw_debug + 2 x isw_wired + 2 x isw_conv + isw_rf = 0.426;
 # the v6/AP4 floorplans hold five switches (0.236): +0.190 is in no floorplan
 'isw_wired': (64081, None, None, 'H', AB, 'PD2 ten islands: v6/AP4 floorplans hold 5 switches = 0.236 of the 0.426'), 'isw_rf': (49817, None, None, 'H', AB, ''),
 'isw_conv': (31781, None, None, 'H', AB, 'PD2 ten islands'), 'isw_debug': (36922, None, None, 'H', AB, 'PD2 ten islands'),
 'prov_supply': (0, None, None, 'H', 'provider ring', ''), 'pad_downbond': (0, None, None, 'M', 'in-ring down-bond site (AGND_RX)', 'no core area; site conflict with POR strap'),
 'pt_agnd_tie': (2000, None, None, 'L', 'estimate (single-point AGND_RX to VSS tie through an ESD structure, PD2-12)', 'NEVER BUILT; in no floorplan'),
 # ---- pads: TRUE occupied core intrusion beyond x=452 / x=3480 (padnotch.json: wirepad/txpad are L-shaped) ----
 'pad_rf_pair': (150969, None, None, 'H', 'v5 floorplan rect clipped to core: 310.06 x 486.91', ''),
 'pad_rftxpad': (150969, None, None, 'H', 'same footprint as pad_rf_pair', ''),
 'pad_refpad': (195358, None, None, 'H', 'v5 floorplan rect clipped: 401.22 x 486.91', ''),
 'pad_single_leg': (147144, None, 99843, 'M', U+' (302.2 x 912.9 drawn); target = undrawn 205 um B cell', 'UNDER-BOOKED in v6/AP4 floorplans: they place WMON at 205 um (pad_single_leg_b, never drawn), the published cell is 302 um: +0.047'),
 'pad_hspad': (327587, 239587, None, 'M', 'published 478.06 x 685.25 in core; staged scratch/pads-core/hspad/b2 492.06 x 486.91 (review pending)', ''),
 'pad_wirepad': (352916, None, 311134, 'H', 'padnotch.json: shell 521.22 x 488.9 + attachment column 187.7 x 522.6; target AP4-6 column 300 um', 'OVER-BOOKED in v6/AP4: bbox 527,214 booked, 174,298 of it is an empty notch (v5 knew it)'),
 'pad_txpad': (278736, None, 257572, 'H', 'padnotch.json: shell 481.22 x 488.9 + column 139.4 x 311.8; target AP4-6 column 160 um', 'OVER-BOOKED in v6/AP4: bbox 385,322 booked, 106,586 is an empty notch'),
 'pad_tlp': (0, None, None, 'H', 'in-ring site 68 x 124 at bidir[25] (PD48b)', 'no core area'),
 'pad_strap': (0, None, None, 'M', 'provider site (freed site)', 'no core area; site conflict POR strap / LNA ground / spare'),
 'pt_host_physical': (0, None, None, 'H', 'provider ring', ''), 'pt_debug_physical': (0, None, None, 'H', 'provider ring', ''),
 'atb_provider_pad': (0, None, None, 'H', 'provider ring', ''),
 'pt_refvcm': (7443, None, None, 'M', 'scratch/pads-core/bias/pub layout (review R10)', 'staged, not published (D-REFVCM); in no floorplan'),
 # ---- RF RX -----------------------------------------------------------------------------------------------------
 'pt_lna': (78352, 42921, None, 'M', 'published = git HEAD generated/lna-layout.json (review R3); staged = working-tree generated/ (uncommitted, design not closed)', 'tail source + gate R still to add (lna_additions row)'),
 'pt_lna_ind': (50000, 35700, 57200, 'L', 'pub = v6 lc_load_rsv 0.10/2; staged 170 um coil (rf-lna-p NOTES l.164); target 4 t d220 57.2k (l.189, +2.3 dB pess)', 'spiral: keep-out 25 um, no MIM/grid/fill over it'),
 'pt_lna_deg': (25200, None, None, 'M', 'rf-lna-p NOTES l.159-160 (G_DEG 140 um 2 t)', 'bench model + generator only; IN NO FLOORPLAN; spiral keep-out'),
 'pt_rxmix_i': (76238, 35442, None, 'M', 'published = git HEAD (review R3); staged = working tree (TIA back to the small option)', ''), 'pt_rxmix_q': (76238, 35442, None, 'M', 'as rxmix_i', ''),
 'pt_bbfilter_i': (341901, None, 230000, 'H', U+'; target AP4-3 (not started)', ''), 'pt_bbfilter_q': (341901, None, 230000, 'H', U, ''),
 'pt_bb_tap': (9978, 19511, None, 'M', 'published = git HEAD 9,978; staged = working tree 19,511 (review R3)', ''),
 # ---- converters ------------------------------------------------------------------------------------------------
 'pt_adc_i': (577710, 449686, 330000, 'M', U+'; staged '+MS+' 480.28 x 936.30 (not published, stage4 not re-reviewed); target AP4-4', 'target missed by 0.12 each'),
 'pt_adc_q': (577785, 449686, 330000, 'M', 'as adc_i', ''),
 'pt_dac_i': (186115, 134121, 130000, 'M', U+'; staged 668.5 x 200.63', ''), 'pt_dac_q': (186115, 134121, 130000, 'M', 'as dac_i', ''),
 'pt_refbuf': (117089, None, None, 'H', U, ''),
 # ---- RF TX -----------------------------------------------------------------------------------------------------
 'pt_txmix_i': (21424, None, None, 'H', U, ''), 'pt_txmix_q': (21424, None, None, 'H', U, ''), 'pt_txsum': (3988, None, None, 'H', U, ''),
 'pt_rfdriver': (96812, None, None, 'H', U, ''),
 # ---- LO ----------------------------------------------------------------------------------------------------------
 'pt_lo_ext': (155350, 133006, 120000, 'M', U+'; staged lo-ap4 cand/run2 343.1 x 387.66 (not qualified)', ''),
 'pt_lo_vreg': (300000, None, None, 'L', 'review R1: scratch/lo-ap4/vreg2/reg.py schematic has ~0.24 mm2 of bare devices (pass devices, 62 MOS-cap units, 90 resistors); 0.25-0.38 at pll_vreg2 utilisation; first estimate here was 0.12', 'NEVER BUILT; still fails 59 dB at 78.125 MHz without an external capacitor (which would need a pad site); in no floorplan'),
 'pt_lc_qvco5': (532476, None, None, 'H', U+' 848 x 627.9', 'two empty corner slots 111 x 303 (lo-ap4 NOTES)'),
 'pt_lo_mmd': (361116, 145031, None, 'M', U+'; staged lo-ap4 377.92 x 383.76 (review NO-GO: -0.2 GHz)', ''),
 'pt_lo_mmd_qdum': (34062, 19124, None, 'M', U+'; staged 97.98 x 195.18', 'fits QVCO slot A'),
 'pt_lo_pfdcp': (124110, None, None, 'H', U, ''), 'pt_lo_lf': (194122, None, None, 'H', U, ''),
 'pt_lo_obs': (17428, 9022, None, 'M', U+'; staged 96.4 x 93.59', 'fits QVCO slot A/B'),
 # ---- clocks / rings ------------------------------------------------------------------------------------------------
 'pt_diff_clk_rx': (22341, None, None, 'H', U, ''), 'pt_clockmux': (15161, None, None, 'H', U, ''), 'pt_prescale': (12600, None, None, 'H', U, ''),
 'pt_pll_vreg2': (173424, None, None, 'H', U, ''),
 'pt_pll_ring_core': (86020, None, 65000, 'H', U+'; target AP4-5c (wired RX, not started)', ''),
 'pt_pll_ring': (166657, None, 127000, 'H', U+'; target: owner says 0.115 unreachable, 0.127 with a core ECO (wired_rx README Resume 9)', ''),
 'pt_cdr': (82901, None, None, 'H', 'r13 published 259.26 x 319.76 (measured)', ''),
 'pt_ring_osc': (9522, None, None, 'H', U, ''), 'pt_vco_replica': (20941, None, None, 'H', U, ''), 'pt_obs_pre4': (3667, None, None, 'H', U, ''),
 'pt_clk_obs16': (92036, 52854, None, 'M', U+'; staged lo-ap4 127.5 x 414.54', ''),
 # ---- wired RX ----------------------------------------------------------------------------------------------------
 'pt_termination': (48249, None, None, 'H', U, ''), 'pt_rxlevel': (13180, None, None, 'H', U, ''),
 'pt_ctle': (133483, 68676, None, 'L', U+'; staged 194 x 354 (review NO-GO, superseded by the follower redesign r4)', 'follower booked separately'),
 'pt_rxselect': (8841, None, None, 'H', U, ''), 'pt_wmon_sel': (9835, None, None, 'H', U, ''),
 'pt_detect': (173480, None, 90000, 'H', U+'; target AP4-1 (layout-only repack FAILED, needs r7i redesign)', ''),
 'pt_wordclk': (24822, None, None, 'H', U, ''), 'pt_vthdac': (23891, None, None, 'H', U, ''),
 'pt_ptrim': (289747, 25938, None, 'L', U+' (published cell not functional); staged ptrim_compact.py 126.4 x 205.2 of the SAME non-functional circuit', 'output stage booked separately'),
 'pt_slicer': (109899, None, None, 'H', U, ''),
 'pt_wrx_cap': (956461, 293813, None, 'M', U+' (r6); staged r7c 1210.55 x 242.71 (NOT publishable: ext_q625_lde60 fails)', ''),
 # ---- wired TX / USB ------------------------------------------------------------------------------------------------
 'pt_wiredtx': (246188, None, None, 'H', U+' (quarter-rate core)', 'eighth-rate growth booked separately (tx8)'),
 'tx_steer': (8677, None, None, 'H', U, 'review R6: steer_0..3 are replaced by the CML pre-drivers booked in tx8_rsv -> not counted; steer_4/5 unused (X5), dropped in C'), 'tx_interlock': (48100, None, None, 'H', AB, ''),
 'term_buffer': (75196, None, 45000, 'H', U+'; target AP4-6', ''),
 'pt_txpad_bias': (12524, None, None, 'M', 'scratch/pads-core/bias/pub layout (review R10)', 'staged, not published (D-TXTERM); in no floorplan'),
 'pt_usb_txdrv': (31457, None, None, 'M', 'USB-INTEGRATION.md l.79: 116.48 x 270.06 (rev 3 not re-reviewed)', 'IN NO FLOORPLAN'),
 'pt_wtx_hsbias': (9137, None, None, 'H', U, ''), 'pt_wtx_fallback_control': (5861, None, None, 'H', U, ''),
 # ---- characterization (D-CHAR: published, IN NO FLOORPLAN) -------------------------------------------------------
 'pt_char_atb': (28239, None, None, 'H', 'characterization/generated/char_atb.lef 192.1 x 147.0', 'IN NO FLOORPLAN'),
 'pt_char_ro33': (9698, None, None, 'H', 'char_ro33.lef 69.64 x 139.26', 'IN NO FLOORPLAN; may duplicate ring_osc (CP4-R4)'),
 'pt_char_ro50': (9320, None, None, 'H', 'char_ro50.lef', 'IN NO FLOORPLAN'), 'pt_char_cmldiv': (27841, None, None, 'H', 'char_cmldiv.lef 104.76 x 265.76', 'IN NO FLOORPLAN'),
 'pt_char_rffet': (111800, None, None, 'H', 'char_rffet.lef 430 x 260 GSG probe frame', 'IN NO FLOORPLAN; needs GLASS openings + probe access'),
 'pt_char_rffet_open': (111800, None, None, 'H', 'as rffet', 'IN NO FLOORPLAN'), 'pt_char_rffet_short': (111800, None, None, 'H', 'as rffet', 'IN NO FLOORPLAN'),
 # ---- ATB / isolation ------------------------------------------------------------------------------------------------
 'atb_grp': (6145, None, None, 'H', AB, ''), 'atb_pad': (6626, None, None, 'H', AB, ''), 'atb_leaf_s': (827, None, None, 'H', AB, ''), 'atb_leaf_f': (1086, None, None, 'H', AB, ''),
 'iso_clamp': (906, None, None, 'H', 'iso-placement.json size_um', 'IN NO FLOORPLAN; CP4-1 already applied in the conn: 130 clamps are AND2 in the macro, 16 + 2 pull-downs stay outside'),
 'iso_clamp_x4': (1025, None, None, 'H', 'iso-placement.json', 'IN NO FLOORPLAN'), 'iso_pd': (95, None, None, 'H', 'iso-placement.json', 'IN NO FLOORPLAN'),
}
# booked items that are not instances of pt_chip.conn: name -> (pub, staged, target, conf, source, note)
BOOKED = {
 'r8arch_slicer_b': (109899, None, None, 'M', 'second slicer bank = pt_slicer outline (AP4 s1 lever 3)', 'R8-ARCH; not in pt_chip.conn'),
 'r8arch_capture_b': (956461, 293813, None, 'M', 'second capture = the capture master of the scenario', 'R8-ARCH; v6 booked it at 0.29 on a master that is still not publishable; literal published master is r6'),
 'r8arch_blend_pd8': (35000, None, None, 'L', 'AP4 s1 lever 3 estimate', 'R8-ARCH'),
 'r8arch_ctle_follower_b': (5000, None, None, 'L', 'wired_rx README Resume 9: one follower per slicer bank, 0.003-0.005', 'R8-ARCH; in no floorplan'),
 'ctle_follower': (5000, None, None, 'L', 'wired_rx README Resume 9 (MW-13-FIX approved): 0.003-0.005 mm2', 'NEVER BUILT; in no floorplan'),
 'ptrim_output_stage': (15000, None, None, 'L', 'estimate: 8 ch x (mid 4/8->12/24, out 8/16->32/64) + CKP0 buffer or doubled channel 0 on the 26k compact cell', 'NEVER BUILT (MW-14-FIX); in no floorplan'),
 'tx8_rsv': (200250, 222000, None, 'L', 'pub = AP4-2 booking 450 x 445; staged = serq8 as built 0.352 (INTEGRATION.md s7) - serq4c 0.158 + 2 CML pre-drivers 0.028', 'eighth-rate / CML not demonstrated (ss 3.24 Gb/s fails): reserve; booking was exceeded'),
 'wtx_tcoil_rsv': (68400, None, None, 'M', 'v5 floorplan rsv_tcoil_wire_tx 570 x 120', 'spiral keep-out'),
 'd2h_gearbox_rsv': (31495, None, None, 'M', 'v5 floorplan rsv_d2h_gearbox 1312.3 x 24', 'W7-GEAR; edge strip'),
 'decap_macro_edge_bank': (390000, None, None, 'M', 'spec/power-delivery.md s4.2: 1.5 nF, within 250 um of the macro W/S/E edges', 'PD2-9; IN NO FLOORPLAN'),
 'supply_clock_monitor': (5000, None, None, 'L', 'review R11: pt_monitor exists as RTL in the macro; outside remain a time base for RF modes and an H2D_CLK present detector', 'D-FAULT'),
 'lna_additions': (10000, None, None, 'L', 'review R12 allowance: LNA tail source, gate R, common-mode damping; D-EXTCLK selector; D-CDRCTL FLL driver', 'counted by nobody'),
 'vcm_buffer': (3000, None, None, 'L', 'estimate (CNV-06: VCM source is a bare 40k divider)', 'counted by nobody'),
 'fwd_clk_repeaters': (3000, None, None, 'L', 'estimate: repeaters/shield for the 3.1 mm AUX_CLK -> wired forwarded clock (CP4-3)', 'counted by nobody'),
}
# Cr = "C realistic": like C, but where the owner has declared the assigned target unreachable or nothing backs it,
# the best backed value is used (review R2, R7 and flags): ADC 0.35 floor, detect and CDR ring unchanged, WMON pad as drawn
CR = {'pt_adc_i': 350000, 'pt_adc_q': 350000, 'pt_detect': 173480, 'pt_pll_ring': 166657, 'pad_single_leg': 147144}
def cols(t):
    pub, st, tg = t[0], t[1], t[2]
    st = pub if st is None else st; tg = st if tg is None else tg
    return pub, st, tg
# CP4-1 (approved, RTL-only): 129 of the 146 clamps become AND2 cells inside the macro in scenarios B and C.
MOVED_ISO = 129
rows = []; moved = 0
for name, d in inst.items():
    m = d['master']; assert m in M, m
    pub, st, tg = cols(M[m]); note = M[m][5]
    if name in ('steer_0', 'steer_1', 'steer_2', 'steer_3'): pub = st = tg = 0; note = 'review R6: replaced by the CML pre-drivers booked in tx8_rsv (double count removed)'
    if name in ('steer_4', 'steer_5'): tg = 0; note = 'unused today (X5 deletes them: target 0)'
    rows.append(dict(item=name, master=m, group=d['group'], kind='conn', pub_um2=pub, staged_um2=st, target_um2=tg, target_backed_um2=CR.get(m, tg), conf=M[m][3], source=M[m][4], note=note))
for name, t in BOOKED.items():
    pub, st, tg = cols(t)
    rows.append(dict(item=name, master='(booked)', group='-', kind='booked', pub_um2=pub, staged_um2=st, target_um2=tg, target_backed_um2=tg, conf=t[3], source=t[4], note=t[5]))
with open(f'{HERE}/ledger.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def cat(r):
    m, it = r['master'], r['item']
    if m == 'pt_digital_macro': return '1 digital macro'
    if m.startswith('pad_') and r['pub_um2'] > 0: return '2 custom pads (true core intrusion)'
    if r['kind'] == 'booked': return '5 booked, not in pt_chip.conn'
    if 'NEVER BUILT' in M[m][5] or 'IN NO FLOORPLAN' in M[m][5]: return '4 in conn, in no floorplan / never built'
    return '3 analog blocks placed by v6/AP4'
tot = collections.OrderedDict(); T = [0, 0, 0, 0]
for r in rows:
    c = tot.setdefault(cat(r), [0, 0, 0, 0, 0])
    for i, k in enumerate(('pub_um2', 'staged_um2', 'target_um2', 'target_backed_um2')):
        c[i] += r[k]; T[i] += r[k]
    c[4] += 1
bym = collections.OrderedDict()
for r in rows:
    k = r['master'] if r['kind'] == 'conn' else r['item']
    e = bym.setdefault(k, dict(n=0, a=[0, 0, 0], conf=r['conf'], src=r['source'], note=r['note'], kind=r['kind']))
    e['n'] += 1
    for i, kk in enumerate(('pub_um2', 'staged_um2', 'target_um2')): e['a'][i] += r[kk]
mm = lambda x: f'{x/1e6:.4f}'
out = ['# Die-fit demand ledger (generated by ledger.py; per-instance rows in ledger.csv)', '',
       f'{len(inst)} instances of pt_chip.conn (commit {CONN_REV}) + {len(BOOKED)} booked items. Areas are core mm2 (pads: true occupied core intrusion).',
       'Ledger v2 (after the independent review, review.md). A = published only, B = everything staged publishes as measured, C = all targets met, Cr = C with unbacked targets replaced. Confidence: H measured on a published GDS/LEF, M measured on a staged or v5 layout, L estimate.', '',
       '| category | items | A published | B staged | C target | Cr target, backed only |', '|---|---:|---:|---:|---:|---:|']
for k in sorted(tot):
    c = tot[k]; out.append(f'| {k} | {c[4]} | {c[0]/1e6:.3f} | {c[1]/1e6:.3f} | {c[2]/1e6:.3f} | {c[3]/1e6:.3f} |')
out += [f'| **total demand** | {len(rows)} | **{T[0]/1e6:.3f}** | **{T[1]/1e6:.3f}** | **{T[2]/1e6:.3f}** | **{T[3]/1e6:.3f}** |',
        f'| core 3028 x 4218 | | {CORE_MM2:.3f} | {CORE_MM2:.3f} | {CORE_MM2:.3f} | {CORE_MM2:.3f} |',
        f'| **raw margin (no routing, halo, decap-over-block, grid)** | | **{CORE_MM2-T[0]/1e6:+.3f}** | **{CORE_MM2-T[1]/1e6:+.3f}** | **{CORE_MM2-T[2]/1e6:+.3f}** | **{CORE_MM2-T[3]/1e6:+.3f}** |', '',
        '## By master / booked item', '', '| item | n | A mm2 | B mm2 | C mm2 | conf | source | flags |', '|---|---:|---:|---:|---:|---|---|---|']
for k, e in sorted(bym.items(), key=lambda kv: -kv[1]['a'][0]):
    out.append(f"| {k}{' (booked)' if e['kind']=='booked' else ''} | {e['n']} | {mm(e['a'][0])} | {mm(e['a'][1])} | {mm(e['a'][2])} | {e['conf']} | {e['src']} | {e['note']} |")
open(f'{HERE}/ledger.md', 'w').write('\n'.join(out)+'\n')
json.dump(dict(rows=rows, totals_um2=T, by_cat={k: v for k, v in tot.items()}, core_mm2=CORE_MM2), open(f'{HERE}/ledger.json', 'w'), indent=0)
print('\n'.join(out[:14]))
nf = sum(r['pub_um2'] for r in rows if cat(r).startswith(('4', '5')))
print('in no floorplan or booked (A):', nf/1e6)
