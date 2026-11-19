#!/usr/bin/env python3
"""Die-area ledger of one chip (current state). One row per instance of integration/chips/<chip>/chip.conn plus booked
items that are not instances (each booked item names the chips that carry it). Every layout number is read from
meas/measured.json (KLayout bounding boxes measured on the GDS on disk by meas/measure.py); nothing is copied from older
tables. Numbers that are not measured carry flag E (estimate).

    CHIP=rf|wired python3 ledger.py          -> <chip>/ledger.csv, <chip>/ledger.json, <chip>/ledger.md

Columns (um2):
  pub      bounding box of the published layout (analog/*/generated), 0 if none
  asbuilt  the newest layout on disk that is meant to ship (a staged repack where one exists, else pub); E if nothing is drawn
  target   the assigned target (area pass 4 / owner), or asbuilt where none is assigned
  lb       defensible lower bound: for a drawn block  bbox - empty20 - 0.5 x (nodev20 - empty20)  of the as-built layout
           (all dead whitespace and half of the device-free channel area recovered), never above target; overrides are stated
Status: P published | U laid out, unpublished | S schematic or generator only | M missing (never designed)
"""
import sys, csv, json, collections, os, subprocess
R = '/home/ubuntu/svalbard'; P = f'{R}/projects/programmable_transceiver_platform'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f'{P}/integration/chips')
import check_top
CHIP = os.environ['CHIP']; assert CHIP in ('rf', 'wired'), 'CHIP=rf|wired'
OUT = f'{HERE}/{CHIP}'; os.makedirs(OUT, exist_ok=True)
inst, ports, waive, err = check_top.parse(check_top.read_conn(f'{P}/integration/chips/{CHIP}/chip.conn'))
assert not err
CONN_REV = subprocess.run(['git', '-C', R, 'log', '-1', '--format=%h', '--', f'{P}/integration/chips'], capture_output=True, text=True).stdout.strip()
MACRO = json.load(open(f'{HERE}/macro.json'))[CHIP]      # per-chip macro outline: synthesis of the chip configuration (split phase 2)
MS = json.load(open(f'{HERE}/meas/measured.json'))
DIE = (3932.0, 5122.0); CORE = (3028.0, 4218.0); CORE_MM2 = CORE[0]*CORE[1]/1e6; RING_DEPTH = 426.0   # pad cells start 26 um inside the die edge; core at 452

def bbox(k): return MS[k]['bbox_um2']
def lbf(k):
    v = MS[k]; return v['bbox_um2'] - v['empty20'] - 0.5*(v['nodev20'] - v['empty20'])
def pad_intr(k):
    """custom pad: (bbox clipped to the core, occupied area inside the core from the 50 um depth bands)"""
    v = MS[k]; box = v['w']*(v['h']-RING_DEPTH); occ = 0.0
    for d, lo, hi in v['bands']:
        a, b = max(d, RING_DEPTH), min(d+50, v['h'])
        if b > a and lo is not None: occ += (hi-lo)*(b-a)
    return box, occ

# master -> dict(pub=key|None, stg=key|um2|None, tgt=um2|None, lb=um2|None|'f', st=status, flag='E' if any number is an estimate, src, lever)
D = dict
M = {
 # ---- digital, always-on ---------------------------------------------------------------------------------------------
 'pt_digital_macro': D(pub=None, stg=MACRO['asbuilt_um2'], tgt=MACRO['target_um2'], lb=MACRO['lb_um2'], st='U', flag='E', src=MACRO['source'],
     lever='RTL reductions (single-rank trims, per-mode duplicates), clock-buffer and gain-buffer area, gated clocks / one read tree (assignment section 4 levers): owner'),
 'por': D(pub='por', st='P', lb=bbox('por'), src='vendored, unmodified', lever='none (no-dead-chip infrastructure)'),
 'pt_aosc': D(pub='pt_aosc', st='P', lever='67 % of the outline has no device: repack to two rows'),
 'pt_core_bias': D(pub='pt_core_bias', tgt=180000, st='U', src='composed by integration builder, scratch/core-bias-routing-20261110-compact (not in generated/); one composite on both chips until the per-chip bank list (D8, D-SPLIT-BIAS)',
     lever='bandgap + biasgen + root + 4 banks + vref measure 0.105 mm2 as cells; the composite is 0.302: 26 % empty, 66 % device-free. Re-place in two abutted rows'),
 'pt_bias_ext': D(pub='CB_pt_bias_tap2', mult=2, st='P', src='two pt_bias_tap2 cells', lever='none'),
 'isw_wired': D(pub='isw_wired', st='P', lever='pass device is 48 % COMP: dense. MIM over it is free decap'),
 'isw_rf': D(pub='isw_rf', st='P', lever='as isw_wired'), 'isw_conv': D(pub='isw_conv', st='P', lever='as isw_wired'), 'isw_debug': D(pub='isw_debug', st='P', lever='as isw_wired'),
 'prov_supply': D(zero='provider ring'), 'prov_supply_sig': D(zero='provider supply cell at a signal site (in the ring)'), 'pad_downbond': D(zero='provider ring site; not available on the fixed bond layout'),
 'pad_strap': D(zero='provider site'), 'pad_tlp': D(zero='in-ring site 68 x 124'), 'pt_host_physical': D(zero='provider ring'),
 'pt_debug_physical': D(zero='provider ring'), 'atb_provider_pad': D(zero='provider ring'),
 'pt_agnd_tie': D(pub=None, stg=2000, st='M', flag='E', src='estimate', lever='-'),
 'pt_refvcm': D(pub='CB_pt_refvcm', st='P', lever='none'),
 # ---- custom pads: handled by pad_intr() ------------------------------------------------------------------------------
 'pad_rf_pair': D(pad='pad_rf_pair'), 'pad_rftxpad': D(pad='pad_rftxpad'), 'pad_refpad': D(pad='pad_refpad'), 'pad_single_leg': D(pad='pad_single_leg'),
 'pad_hspad': D(pad='pad_hspad'), 'pad_wirepad': D(pad='pad_wirepad'), 'pad_txpad': D(pad='pad_txpad'),
 # ---- RF RX (owner active: analog/rf_rx) ----------------------------------------------------------------------------
 'pt_lna': D(pub='pt_lna', st='U', src='working tree, uncommitted; design not closed (LNA NO-GO)', lever='owner'),
 'pt_lna_ind': D(pub='pt_lna_ind', st='U', lb=bbox('pt_lna_ind'), src='working-tree generated/lna_ind.gds 260 x 266', lever='spiral: no lever'),
 'pt_lna_deg': D(pub=None, stg=25200, st='S', flag='E', src='generator + bench model only (140 um, 2 turns); rf-lna-p NOTES', lever='spiral'),
 'pt_rxmix_i': D(pub='pt_rxmix_i', st='U', src='working tree (small TIA option)', lever='dense'), 'pt_rxmix_q': D(pub='pt_rxmix_q', st='U', src='as rxmix_i', lever='dense'),
 'pt_bbfilter_i': D(pub='pt_bbfilter_i', tgt=230000, st='P', lever='25 % of the outline empty, 61 % device-free; MIM 0.034 could sit over the amplifiers'),
 'pt_bbfilter_q': D(pub='pt_bbfilter_q', tgt=230000, st='P', lever='as bbfilter_i'),
 'pt_bb_tap': D(pub='pt_bb_tap', st='U', src='working tree', lever='37 % device-free'),
 # ---- converters ------------------------------------------------------------------------------------------------------
 'pt_adc_i': D(pub='pt_adc_i', stg='STG_pt_adc_i', tgt=330000, st='U', src='staged stage4 (not re-reviewed, sims unfinished)',
     lever='staged cell still 20 % empty, 67 % device-free: Metal3 channel bank and two 120 x 75 macro rows in a 408 um row'),
 'pt_adc_q': D(pub='pt_adc_q', stg='STG_pt_adc_i', tgt=330000, st='U', src='as adc_i (staged I and Q have the same outline)', lever='as adc_i'),
 'pt_dac_i': D(pub='pt_dac_i', stg='STG_pt_dac_i', tgt=130000, st='U', src='staged stage4', lever='dac_logic macro re-harden 640 x 75 -> 640 x 48'),
 'pt_dac_q': D(pub='pt_dac_q', stg='STG_pt_dac_i', tgt=130000, st='U', src='as dac_i', lever='as dac_i'),
 'pt_refbuf': D(pub='pt_refbuf', st='P', lever='0.055 mm2 of MIM beside the amplifier; 24 % of the outline empty: MIM over the devices'),
 # ---- RF TX -----------------------------------------------------------------------------------------------------------
 'pt_txmix_i': D(pub='pt_txmix_i', st='P', lever='30 % empty'), 'pt_txmix_q': D(pub='pt_txmix_q', st='P', lever='30 % empty'),
 'pt_txsum': D(pub='pt_txsum', st='P', lever='dense'), 'pt_rfdriver': D(pub='pt_rfdriver', st='P', lever='40 % device-free (output routing)'),
 # ---- LO (paused pending a decision: analysis only) ----------------------------------------------------------------
 'pt_lo_ext': D(pub='pt_lo_ext', stg='STG_pt_lo_ext', tgt=120000, st='U', src='staged candidate, not qualified', lever='LO owner'),
 'pt_lo_vreg': D(pub=None, stg='STG_pt_lo_vreg', tgt=300000, st='U', src='staged scratch/lo-ap4/vreg2 407 x 1082; to be requalified against -60 dBc and shrunk',
     lever='47 % COMP (pass devices + MOS caps). Spur limit relaxed 20 dB: hold capacitors and the second follower stage can shrink'),
 'pt_lc_qvco5': D(pub='pt_lc_qvco5', st='P', lb=848.0*627.92, phys=(848.0, 627.92), src='bbox 898 x 653 includes a 25 um keep-out on three sides; drawn metal 848 x 628',
     lever='two corner slots hold qdum + lo_obs (coupling not quantified)'),
 'pt_lo_mmd': D(pub='pt_lo_mmd', stg='STG_pt_lo_mmd', st='U', src='staged; review NO-GO (maximum frequency regressed)', lever='LO owner'),
 'pt_lo_mmd_qdum': D(pub='pt_lo_mmd_qdum', stg='STG_pt_lo_mmd_qdum', st='U', src='staged', lever='QVCO corner slot'),
 'pt_lo_pfdcp': D(pub='pt_lo_pfdcp', st='P', lever='41 % device-free'),
 'pt_lo_lf': D(pub='pt_lo_lf', st='P', tgt=None, lb=194122-45000, src='C2 = 490 pF MOS capacitor is 0.136 of it',
     lever='MIM stacked over the C2 MOS capacitor: 0.04-0.05; or C2 off-chip (OCP-1, 0.12-0.15, needs OCP-2)'),
 'pt_lo_obs': D(pub='pt_lo_obs', stg='STG_pt_lo_obs', st='U', src='staged', lever='QVCO corner slot'),
 # ---- clocks / rings (owner active: analog/timing) --------------------------------------------------------------------
 'pt_diff_clk_rx': D(pub='pt_diff_clk_rx', st='P', lever='38 % device-free'), 'pt_clockmux': D(pub='pt_clockmux', st='P', lever='16 % empty, 53 % device-free'),
 'pt_prescale': D(pub='pt_prescale', st='P', lever='CP4-7: prescale + prescale_conv as one chain'),
 'pt_pll_vreg2': D(pub='pt_pll_vreg2', st='P', lever='dense (48 % COMP)'),
 'pt_pll_ring_core': D(pub='pt_pll_ring_core', tgt=65000, st='P', lever='37 % device-free'),
 'pt_pll_ring': D(pub='pt_pll_ring', tgt=127000, st='P', lever='slab-collapse of the device-free band y 258-447'),
 'pt_cdr': D(pub='pt_cdr', st='P', lever='dense (r13)'),
 'pt_ring_osc': D(pub='pt_ring_osc', st='P', lever='CP4-R4: same structure as pt_char_ro33?'), 'pt_vco_replica': D(pub='pt_vco_replica', st='P', lever='-'),
 'pt_obs_pre4': D(pub='pt_obs_pre4', st='P', lever='CP4-4: two of six replaced by ring FBCK'),
 'pt_clk_obs16': D(pub='pt_clk_obs16', stg='STG_pt_clk_obs16', st='U', src='staged', lever='dense'),
 'pt_wordclk': D(pub='pt_wordclk', st='P', lever='CP4-8: counter into pt_wrx_cap'),
 # ---- wired RX (owner active) ------------------------------------------------------------------------------------------
 'pt_termination': D(pub='pt_termination', st='P', lever='42 % device-free'), 'pt_rxlevel': D(pub='pt_rxlevel', st='P', lever='dense'),
 'pt_ctle': D(pub='pt_ctle', stg=68676, st='U', flag='E', src='staged 194 x 354 per the owner (NO-GO, superseded by the follower redesign): not re-measured, no current GDS', lever='owner'),
 'pt_rxselect': D(pub='pt_rxselect', st='P', lever='-'), 'pt_wmon_sel': D(pub='pt_wmon_sel', st='P', lever='-'),
 'pt_detect': D(pub='pt_detect', tgt=90000, st='P', lever='71 % device-free; layout-only repack failed its thresholds: needs the r7i redesign'),
 'pt_vthdac': D(pub='pt_vthdac', st='P', lever='-'),
 'pt_ptrim': D(pub='pt_ptrim', stg=45000, st='U', flag='E', src='published 449 x 645 cell is not functional; redesign candidates l2-l6 are 188-227 x 211 um per scratch/wired_rx/r10ptrim/STATUS.md (no top GDS found)', lever='owner'),
 'pt_slicer': D(pub='pt_slicer', st='P', lever='47 % device-free'),
 'pt_wrx_cap': D(pub='pt_wrx_cap', stg='STG_pt_wrx_cap', st='U', src='staged r7c (fails one extracted case)', lever='dense after the repack'),
 # ---- wired TX / USB (owner active) -----------------------------------------------------------------------------------
 'pt_wiredtx': D(pub='pt_wiredtx', stg=bbox('pt_wiredtx')-bbox('STG_wtx_serq4c'), st='U', flag='E',
     src='published 543.9 x 452.7 less the quarter-rate core wtx_serq4c (530 x 308, measured) that the new path replaces; no block top of the new transmitter exists', lever='owner'),
 'tx_steer': D(pub='tx_steer', st='P', lever='steer_0..3 retire with the new transmit path (WT34), steer_4/5 unused (X5)'),
 'tx_interlock': D(pub='tx_interlock_thick', tgt=30000, st='P', lever='TMDS half tied off (CP4-R3)'),
 'term_buffer': D(pub='term_buffer', tgt=45000, st='P', lever='24 % empty, 76 % device-free'),
 'pt_txpad_bias': D(pub='CB_pt_txpad_bias', st='P', lever='CP4-10: a tap of the termination divider'),
 'pt_usb_txdrv': D(pub='pt_usb_txdrv', st='P', src='rev 3 unreviewed', lever='dense'),
 'pt_wtx_hsbias': D(pub='pt_wtx_hsbias', st='P', lever='-'), 'pt_wtx_fallback_control': D(pub='pt_wtx_fallback_control', st='P', lever='-'),
 # ---- characterization ------------------------------------------------------------------------------------------------
 'pt_char_atb': D(pub='pt_char_atb', st='P', lever='45 % empty'), 'pt_char_ro33': D(pub='pt_char_ro33', st='P', lever='-'),
 'pt_char_ro50': D(pub='pt_char_ro50', st='P', lever='-'), 'pt_char_cmldiv': D(pub='pt_char_cmldiv', st='P', lever='36 % empty'),
 'pt_char_rffet': D(pub='pt_char_rffet', st='P', lb=260.0*220.0, src='rebuilt 2026-11-18 (was 430 x 260): port pad centres 200 um, ground rails inside the pad columns',
     lever='stack the three frames at 200 um pitch sharing ground pads (260 x 660, checked by rffet.py stack): assembly'),
 'pt_char_rffet_open': D(pub='pt_char_rffet_open', st='P', lb=260.0*220.0, src='as rffet', lever='as rffet'),
 'pt_char_rffet_short': D(pub='pt_char_rffet_short', st='P', lb=260.0*220.0, src='as rffet', lever='as rffet'),
 # ---- ATB / isolation ---------------------------------------------------------------------------------------------------
 'atb_grp': D(pub='atb_grp', st='P', lever='-'), 'atb_pad': D(pub='atb_pad', st='P', lever='-'),
 'atb_leaf_s': D(pub='atb_leaf_s', st='P', lever='58 leaves of 30.6 x 27.0: abut in rows with a shared guard ring'),
 'atb_leaf_f': D(pub='atb_leaf_f', st='P', lever='as atb_leaf_s'),
 'iso_clamp': D(pub='iso_clamp', st='P', lever='-'), 'iso_clamp_x4': D(pub='iso_clamp_x4', st='P', lever='-'), 'iso_pd': D(pub='iso_pd', st='P', lever='-'),
}
# per-instance overrides: name -> (asbuilt, target, lb, note)
INST = {
 'steer_0': (0, 0, 0, 'retires with the new transmit path (WT34/WT36)'), 'steer_1': (0, 0, 0, 'as steer_0'), 'steer_2': (0, 0, 0, 'as steer_0'), 'steer_3': (0, 0, 0, 'as steer_0'),
 'steer_4': (None, 0, 0, 'unused today (X5)'), 'steer_5': (None, 0, 0, 'unused today (X5)'),
 'pad_bb_i': (None, None, 0, 'lb: provider asig_5p0 cell, no core intrusion (AP4-7)'), 'pad_bb_q': (None, None, 0, 'as pad_bb_i'),
 'pad_wmon': (None, 205.0*486.91, 0, 'target: 205 um B cell (undrawn); lb: provider cell (AP4-7)'),
 'pad_wtx_ext': (None, None, None, 'OCP-2 closed (D7): WTX_EXT keeps its own pads on pt_wired'),
 'lo_mmd_qdum': (None, None, 0, 'lb: inside the QVCO outline (slot A)'), 'lo_obs': (None, None, 0, 'lb: inside the QVCO outline'),
 'obs_pre4_pll': (None, None, 0, 'lb: CP4-4'), 'obs_pre4_cdr': (None, None, 0, 'lb: CP4-4'), 'prescale_conv': (None, None, 0, 'lb: CP4-7'),
 'wordclk_rx': (None, None, 0, 'lb: CP4-8'), 'txpad_bias': (None, None, 0, 'lb: CP4-10'),
}
# booked items that are not instances of the chip conns: (asbuilt, target, lb, status, flag, source); BOOKED_CHIP names the chips
BOOKED = {
 'wtx_ser8d': (bbox('STG_wtx_ser8d'), None, lbf('STG_wtx_ser8d'), 'U', '', 'new transmit path stream macro, generated/fast (unpublished), measured'),
 'wtx_mux8': (bbox('STG_wtx_mux8'), None, bbox('STG_wtx_mux8'), 'U', '', 'new transmit path muxing pre-driver, scratch/wired_tx/s12 rev2, measured'),
 'r8arch_slicer_b': (bbox('pt_slicer'), None, None, 'S', 'E', 'second slicer bank for > 2.5 Gb/s receive = pt_slicer outline; architecture not designed'),
 'r8arch_capture_b': (bbox('STG_pt_wrx_cap'), None, None, 'S', 'E', 'second capture = staged r7c outline; not designed'),
 'r8arch_blend_pd8': (35000, None, None, 'M', 'E', 'estimate (area pass 4)'),
 'ctle_follower_x2': (10000, None, None, 'M', 'E', 'two CTLE source followers (MW-13-FIX), 0.003-0.005 each'),
 'wtx_tcoil_rsv': (68400, None, None, 'M', 'E', 'TX T-coil reserve 570 x 120 (v5 floorplan)'),
 'd2h_strip': (31495, None, None, 'M', 'E', 'D2H output strip / pad repeaters 1312 x 24 at the south pad row'),
 'decap_macro_edge_bank': (390000, None, None, 'S', 'E', '1.5 nF bank of pt_decap_tile + MIM within 250 um of the macro (power-delivery.md 4.2); tile cell published, bank not drawn. Kept on both chips (D9: full 5.4 nF)'),
 'decap_tiles': (None, None, None, 'S', 'E', 'stacked MOS + MIM tiles (pt_decap_tile + MIM, 4 fF/um2) for the part of the 5.4 nF plan that the bank, grid MIM over the blocks, macro row fill and bond-site tiles do not give (decap.json, D9)'),
 'rf_timebase_h2dclk_detect': (5000, None, None, 'M', 'E', 'time base for RF modes + H2D_CLK present detector (rest of the monitor is RTL)'),
 'lna_additions': (10000, None, None, 'M', 'E', 'LNA tail source, gate R, damping; D-EXTCLK selector; FLL driver'),
 'vcm_buffer': (3000, None, None, 'M', 'E', 'CNV-06: the VCM source is a bare divider'),
 'fwd_clk_repeaters': (3000, None, None, 'M', 'E', 'repeaters / shield for the AUX_CLK to wired forwarded clock (short on pt_wired: the pad pair is on the same chip as the CDR)'),
}
BOOKED_CHIP = {'wtx_ser8d': 'wired', 'wtx_mux8': 'wired', 'r8arch_slicer_b': 'wired', 'r8arch_capture_b': 'wired', 'r8arch_blend_pd8': 'wired',
               'ctle_follower_x2': 'wired', 'wtx_tcoil_rsv': 'wired', 'fwd_clk_repeaters': 'wired', 'lna_additions': 'rf', 'vcm_buffer': 'rf',
               'd2h_strip': 'both', 'decap_macro_edge_bank': 'both', 'decap_tiles': 'both', 'rf_timebase_h2dclk_detect': 'both'}
assert set(BOOKED_CHIP) == set(BOOKED)
BOOKED = {k: v for k, v in BOOKED.items() if BOOKED_CHIP[k] in ('both', CHIP)}
DEC = json.load(open(f'{HERE}/decap.json')).get(CHIP) if os.path.exists(f'{HERE}/decap.json') else None   # tiles per scenario (decap.py; first pass: 0)
DEC = DEC or dict(tiles_um2=dict(asbuilt=0, target=0, lb=0))
BOOKED['decap_tiles'] = (DEC['tiles_um2']['asbuilt'], DEC['tiles_um2']['target'], DEC['tiles_um2']['lb']) + BOOKED['decap_tiles'][3:]

rows = []
def add(item, master, group, kind, pub, ab, tg, lb, st, flag, src, lever, shape=None, mkey=''):
    tg = ab if tg is None else min(tg, ab) if kind != 'pad' else tg
    lb = tg if lb is None else min(lb, tg)
    rows.append(dict(item=item, master=master, group=group, kind=kind, status=st, est=flag, pub_um2=round(pub), asbuilt_um2=round(ab), target_um2=round(tg),
                     lb_um2=round(lb), w=shape[0] if shape else '', h=shape[1] if shape else '', mkey=mkey or '', source=src, lever=lever))
for name, d in inst.items():
    m = d['master']; e = M[m]; g = d['group']
    if 'zero' in e:
        add(name, m, g, 'conn', 0, 0, 0, 0, 'P', '', e['zero'], '-'); continue
    if 'pad' in e:
        box, occ = pad_intr(e['pad']); v = MS[e['pad']]
        ab = occ; tg = occ; lb = occ; note = f"published {v['w']} x {v['h']}; bbox inside the core {box/1e6:.4f}, occupied (50 um depth bands) {occ/1e6:.4f}"
        lever = {'pad_wirepad': 'attachment column repack (AP4-6a); ESD rows under the rail band (AP4-6b)', 'pad_txpad': 'as wirepad; 0.6x MAIN switch (WT34)',
                 'pad_hspad': 'stacked cell is published', 'pad_refpad': 'taper: 401 um wide at the ring, 318 um at the tip'}.get(m, 'ESD rows under the provider rail band (AP4-6b)')
        o = INST.get(name)
        if o:
            tg = o[1] if o[1] is not None else tg; lb = o[2] if o[2] is not None else lb; note += '; ' + o[3]
        if m == 'pad_wirepad': tg = occ - 174298*0 - (522.6-300.0)*187.7; note += '; target: attachment column 523 -> 300 um deep'
        if m == 'pad_txpad': tg = occ - (311.8-160.0)*139.4; note += '; target: column 312 -> 160 um'
        add(name, m, g, 'pad', box, ab, min(tg, ab), min(lb, tg), 'P', '', note, lever, (v['w'], v['h'])); continue
    mult = e.get('mult', 1)
    pub = bbox(e['pub'])*mult if e.get('pub') else 0
    stg = e.get('stg'); key = stg if isinstance(stg, str) else e.get('pub')
    ab = bbox(stg) if isinstance(stg, str) else stg if stg is not None else pub
    if 'phys' in e: ab = e['phys'][0]*e['phys'][1]
    lb = e.get('lb')
    if lb is None and key and not e.get('flag') and 'empty20' in MS[key]: lb = lbf(key)*mult
    shape = e.get('phys') or ((MS[key]['w'], MS[key]['h']) if key and mult == 1 and not (e.get('flag') and not isinstance(stg, str)) else None)
    tg = e.get('tgt'); src = e.get('src', ''); o = INST.get(name)
    if o:
        ab = o[0] if o[0] is not None else ab; tg = o[1] if o[1] is not None else tg; lb = o[2] if o[2] is not None else lb; src = (src + '; ' if src else '') + o[3]
    add(name, m, g, 'conn', pub, ab, tg, lb, e['st'], e.get('flag', ''), src, e.get('lever', ''), shape, key if (key and 'empty20' in MS.get(key, {}) and ab > 0 and abs(bbox(key)*mult-ab) < 0.12*ab) else '')
for name, (ab, tg, lb, st, flag, src) in BOOKED.items():
    k = {'wtx_ser8d': 'STG_wtx_ser8d', 'wtx_mux8': 'STG_wtx_mux8', 'r8arch_slicer_b': 'pt_slicer', 'r8arch_capture_b': 'STG_pt_wrx_cap'}.get(name)
    add(name, '(booked)', 'wired_tx' if name.startswith('wtx') else '-', 'booked', 0, ab, tg, lb, st, flag, src,
        {'decap_macro_edge_bank': 'lb 0 = no dedicated bank (decap 5.4 -> 3.9 nF or stacked tiles elsewhere): power delivery decision',
         'wtx_ser8d': '47 % device-free: routing channels are 127 of 315 um of height (owner lever)'}.get(name, '-'), (MS[k]['w'], MS[k]['h']) if k else None, k or '')

with open(f'{OUT}/ledger.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
def cat(r):
    if r['master'] == 'pt_digital_macro': return '1 digital macro'
    if r['kind'] == 'pad': return '2 custom pads (occupied core intrusion)'
    if r['kind'] == 'booked': return '4 booked, not instances of the conn'
    return '3 analog blocks in the conn'
K = ('pub_um2', 'asbuilt_um2', 'target_um2', 'lb_um2')
tot = collections.OrderedDict(); T = [0]*4; est = [0]*4
for r in rows:
    c = tot.setdefault(cat(r), [0, 0, 0, 0, 0]); c[4] += 1
    for i, k in enumerate(K):
        c[i] += r[k]; T[i] += r[k]
        if r['est']: est[i] += r[k]
bym = collections.OrderedDict()
for r in rows:
    k = r['master'] if r['kind'] != 'booked' else r['item']
    e = bym.setdefault(k, dict(n=0, a=[0]*4, r=r)); e['n'] += 1
    for i, kk in enumerate(K): e['a'][i] += r[kk]
mm = lambda x: f'{x/1e6:.4f}'
SN = {'P': 'published', 'U': 'laid out, unpublished', 'S': 'schematic / generator only', 'M': 'missing'}
out = [f'# Die-area ledger of pt_{CHIP} (generated by ledger.py; per-instance rows in ledger.csv)', '',
       f'{len(inst)} instances of `integration/chips/{CHIP}/chip.conn` (commit {CONN_REV}) + {len(BOOKED)} booked items. Core mm2. Layout numbers are KLayout bounding boxes measured on the GDS on disk (`meas/measured.json`); **E** marks every row that contains an estimate.', '',
       '| category | items | published | as built | target | lower bound |', '|---|---:|---:|---:|---:|---:|']
for k in sorted(tot):
    c = tot[k]; out.append(f'| {k} | {c[4]} | {c[0]/1e6:.3f} | {c[1]/1e6:.3f} | {c[2]/1e6:.3f} | {c[3]/1e6:.3f} |')
out += [f'| **block demand** | {len(rows)} | | **{T[1]/1e6:.3f}** | **{T[2]/1e6:.3f}** | **{T[3]/1e6:.3f}** |',
        f'| of it estimates (E rows) | | | {est[1]/1e6:.3f} | {est[2]/1e6:.3f} | {est[3]/1e6:.3f} |',
        f'| core {CORE[0]:.0f} x {CORE[1]:.0f} | | | {CORE_MM2:.3f} | {CORE_MM2:.3f} | {CORE_MM2:.3f} |',
        f'| **raw margin (before channels, corridors, scrap)** | | | **{CORE_MM2-T[1]/1e6:+.3f}** | **{CORE_MM2-T[2]/1e6:+.3f}** | **{CORE_MM2-T[3]/1e6:+.3f}** |', '',
        '## By master', '', '| item | n | status | E | W x H um (as built) | published | as built | target | lower bound | empty / device-free | source, notes |', '|---|---:|---|---|---|---:|---:|---:|---:|---|---|']
def dens(r):
    e = M.get(r['master'], {}); stg = e.get('stg'); key = stg if isinstance(stg, str) else e.get('pub')
    if r['kind'] == 'booked': key = {'wtx_ser8d': 'STG_wtx_ser8d', 'wtx_mux8': 'STG_wtx_mux8'}.get(r['item'])
    if key and key in MS and 'empty20' in MS[key]:
        v = MS[key]; return f"{100*v['empty20']/v['bbox_um2']:.0f} % / {100*v['nodev20']/v['bbox_um2']:.0f} %"
    return ''
for k, e in sorted(bym.items(), key=lambda kv: -kv[1]['a'][1]):
    r = e['r']; wh = f"{r['w']} x {r['h']}" if r['w'] else ''
    out.append(f"| {k} | {e['n']} | {SN[r['status']]} | {r['est']} | {wh} | {mm(e['a'][0])} | {mm(e['a'][1])} | {mm(e['a'][2])} | {mm(e['a'][3])} | {dens(r)} | {r['source']} |")
open(f'{OUT}/ledger.md', 'w').write('\n'.join(out)+'\n')
json.dump(dict(chip=CHIP, rows=rows, totals_um2=T, est_um2=est, by_cat={k: v for k, v in tot.items()}, core_mm2=CORE_MM2), open(f'{OUT}/ledger.json', 'w'), indent=0)
print('\n'.join(out[:14]))
