#!/usr/bin/env python3
"""Die-fit of one chip: packing attempt on the fixed die with the real packer (packer.py).

  CHIP=rf|wired SCEN=S|T|LB  [HALO=10] [MACRO=W:x0,...] [BANK=1] [TILES=1] [TAG=..]  python3 fit.py
  S = as built (newest layout on disk), T = targets met, LB = every block at its defensible lower bound (ledger.py).
Inputs: <chip>/ledger.json (areas and measured shapes, decap tiles from decap.py), the chip's bond map and the provider
site coordinates (custom pad positions), consolidation-pass-4 inventory.csv (worst currents), netcounts.json (signal
counts per instance). Outputs: run/<chip>/fit-<tag>.json, run/<chip>/fit-<tag>.png.  No design file is touched.
"""
import os, sys, json, math, csv, re, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); R = '/home/ubuntu/svalbard'
sys.path.insert(0, HERE)
from packer import Packer, overlap_check

CHIP = os.environ['CHIP']; assert CHIP in ('rf', 'wired')
P_ = f'{R}/projects/programmable_transceiver_platform'
SCEN = os.environ.get('SCEN', 'S'); HALO = float(os.environ.get('HALO', '10')); TAG = os.environ.get('TAG', SCEN.lower())
BANK = os.environ.get('BANK', '1') == '1'           # dedicated macro-edge decap bank (0.39 mm2)
TILES = os.environ.get('TILES', '1') == '1'         # decap tiles for the rest of the 5.4 nF plan (decap.py), 125 x 120 um each
CORRIDOR = os.environ.get('CORRIDOR', '1') == '1'   # N-S bus corridor from the macro to the south pad row
DROP = set(filter(None, os.environ.get('DROP', '').split(',')))   # lever experiments: items removed from the inventory
MACROS = [tuple(float(v) for v in m.split(':')) for m in os.environ.get('MACRO', '1716:1108,1716:1262').split(',')]
GROW = float(os.environ.get('GROW', '0'))          # information only: die/core made taller by GROW um (north edge moves)
NOPAD = set(filter(None, os.environ.get('NOPAD', '').split(',')))   # lever experiments: custom pads with zero core intrusion
ISLW = float(os.environ.get('ISLAND_W', '0.05'))   # pull of an island block to its switch per mA (assembly raises it to group islands)
TRIES = int(os.environ.get('TRIES', '1')); SEED = int(os.environ.get('SEED', '1'))
RING = float(os.environ.get('RING', '0'))          # AP4-10b: core ring narrowed, core edge moves out by RING um on every side
DIE = (0.0, 0.0, 3932.0, 5122.0+GROW); CORE = (452.0-RING, 452.0-RING, 3480.0+RING, 4670.0+GROW+RING)
L = json.load(open(f'{HERE}/{CHIP}/ledger.json')); KEY = {'S': 'asbuilt_um2', 'T': 'target_um2', 'LB': 'lb_um2'}[SCEN.upper()]; SCEN = SCEN.upper()
ROW = {r['item']: r for r in L['rows']}
MACRO_A = float(os.environ.get('MACRO_MM2', 0))*1e6 or float(ROW['digital'][KEY])   # digital macro outline area of the scenario
mA = {r['inst']: float(r['mA_worst']) for r in csv.DictReader(open(f'{R}/scratch/reviews/consolidation-pass-4/inventory.csv'))}
mA.update(wordclk_rx=2.42, clk_obs=4.96, usb_txdrv=20.0, lo_vreg=1.0, wtx_mux8=28.0, wtx_ser8d=10.0, wiredtx=5.0)
nc = json.load(open(f'{HERE}/netcounts.json'))

# ---- shapes: measured W x H of the ledger row (scaled to the scenario area), unknown blocks square ----------------------
SHAPE = {'tx_interlock': (139.4, 345.0), 'pt_ptrim': (190.0, 211.2), 'pt_lo_vreg': (407.4, 1081.6), 'pt_ctle': (194.0, 354.0), 'pt_wiredtx': (543.9, 152.0),
         'd2h_strip': (1312.3, 24.0), 'wtx_tcoil_rsv': (570.0, 120.0)}
SIZES = json.load(open(os.environ['SIZES_JSON'])) if os.environ.get('SIZES_JSON') else {}
ITEM_SIZES = json.loads(os.environ.get('ITEM_SIZES', '{}'))
HALO_ITEMS = json.loads(os.environ.get('HALO_ITEMS', '{}'))   # assembly: per-item halo (routing room round busy blocks)   # item -> [w, h] (assembly: a booking that stands for a group)   # master -> [w, h] measured on the GDS (assembly flow)
def shape(r, area):
    if ITEM_SIZES.get(r['item']): return tuple(ITEM_SIZES[r['item']])
    if SIZES.get(r['master']): return tuple(SIZES[r['master']])
    w, h = (float(r['w']), float(r['h'])) if r['w'] else SHAPE.get(r['master'] if r['kind'] == 'conn' else r['item'], (1, 1))
    k = math.sqrt(area/(w*h)); k = 1.0 if abs(k-1) < 0.012 else k
    return round(w*k, 2), round(h*k, 2)

FIXED_ITEMS = {'wtx_tcoil_rsv', 'd2h_strip', 'decap_macro_edge_bank', 'decap_tiles'}
SPIRAL = ('lna_ind', 'lna_deg', 'qvco')
blocks = {}
for r in L['rows']:
    a = r[KEY]; n = r['item']; m = r['master']
    if a <= 0 or r['kind'] == 'pad' or m.startswith('pad_') or m == 'pt_digital_macro' or n in FIXED_ITEMS or n in DROP:
        continue
    w, h = shape(r, a)
    small = a < 2500
    blocks[n] = dict(w=w, h=h, grp=r['group'], master=m, halo=float(HALO_ITEMS.get(n, 4.0 if small else 25.0 if n.startswith(SPIRAL) else HALO)),
                     rot=True, mA=mA.get(n, 0.0), nets=nc['ctl_per_inst'].get(n, 0)+nc['direct_per_inst'].get(n, 0))
for n in filter(None, os.environ.get('NOROT', '').split(',')):     # assembly: blocks that must stay unrotated (grid phase)
    if n in blocks: blocks[n]['rot'] = False
# side-pin channels: compact ptrim has PH/CKP/T pins (56) on one edge -> 32 um pin channel is part of its footprint
if 'ptrim' in blocks: blocks['ptrim']['w'] += 32.0
if BANK and ROW['decap_macro_edge_bank'][KEY] > 0:
    for i in range(26):
        blocks[f'decap_bank_{i:02d}'] = dict(w=125.0, h=120.0, grp='core', master='decap', halo=0.0, rot=True, mA=0, nets=0)
if TILES and ROW.get('decap_tiles', {}).get(KEY, 0) > 0:      # stacked MOS + MIM tiles: any hole, placed last (no flow partner)
    for i in range(math.ceil(ROW['decap_tiles'][KEY]/15000.0)):
        blocks[f'decap_tile_{i:02d}'] = dict(w=125.0, h=120.0, grp='core', master='decap', halo=0.0, rot=True, mA=0, nets=0)

# ---- signal-flow / supply targets ---------------------------------------------------------------------------------------
T = {
 'lna': [('pad_rf_rx', 3), ('isw_rf_rx', 1)], 'lna_ind_p': [('lna', 3)], 'lna_ind_n': [('lna', 3)], 'lna_deg_p': [('lna', 3)], 'lna_deg_n': [('lna', 3)],
 'rxmix_i': [('lna', 2), ('lo_ext', 1)], 'rxmix_q': [('lna', 2), ('lo_ext', 1)], 'bbfilter_i': [('rxmix_i', 2), ('lna', 1)], 'bbfilter_q': [('rxmix_q', 2), ('lna', 1)],
 'adc_i': [('bbfilter_i', 2), ('digital', 0.3)], 'adc_q': [('bbfilter_q', 2), ('digital', 0.3)], 'refbuf': [('adc_i', 1), ('adc_q', 1), ('dac_i', 0.5)],
 'bb_tap_i': [('bbfilter_i', 1), ('pad_bb_i', 2)], 'bb_tap_q': [('bbfilter_q', 1), ('pad_bb_q', 2)], 'bb_tap_wmon': [('wmon_sel', 1), ('pad_wmon', 2)],
 'dac_i': [('txmix_i', 2), ('rfdriver', 1), ('digital', 0.3)], 'dac_q': [('txmix_q', 2), ('rfdriver', 1), ('digital', 0.3)],
 'txmix_i': [('rfdriver', 2), ('lo_ext', 0.5)], 'txmix_q': [('rfdriver', 2), ('lo_ext', 0.5)], 'txsum': [('rfdriver', 3)],
 'rfdriver': [('pad_rf_tx', 3), ('isw_rf_tx', 1)],
 'qvco': [('isw_lo', 2), ('pad_ref', 0.5)], 'lo_vreg': [('qvco', 3), ('isw_lo', 1)], 'lo_mmd': [('qvco', 4)], 'lo_mmd_qdum': [('qvco', 4)],
 'lo_obs': [('qvco', 3)], 'lo_obs_q': [('qvco', 3)], 'lo_pfdcp': [('qvco', 1), ('lo_lf', 2), ('lo_mmd', 1)], 'lo_lf': [('qvco', 2)],
 'lo_ext': [('pad_ref', 2), ('pad_aux_clk', 2), ('qvco', 1), ('rxmix_i', 0.5)],
 'rx_ref_in': [('pad_ref', 3)], 'rx_aux_clk': [('pad_aux_clk', 3)], 'rx_wtx_ext': [('pad_wtx_ext', 3)], 'refvcm': [('pad_ref', 2)],
 'clockmux': [('pll_cdr', 1), ('pll_tx', 1), ('rx_ref_in', 0.5)], 'prescale': [('clockmux', 2)], 'prescale_conv': [('clockmux', 1), ('adc_i', 1)],
 'prescale_hf': [('clockmux', 2)], 'pll_vreg2': [('pll_cdr', 2), ('pll_tx', 2), ('isw_pll', 1)], 'pll_tx': [('wiredtx', 3)],
 'pll_cdr': [('ptrim', 3), ('cdr', 1)], 'cdr': [('pll_cdr', 2), ('wrx_cap', 1)], 'wordclk_rx': [('wrx_cap', 2)],
 'termination': [('pad_hs_rx', 3)], 'ctle': [('pad_hs_rx', 3)], 'ctle_follower': [('ctle', 5)], 'rxselect': [('ctle', 2)], 'rxlevel': [('termination', 2)],
 'slicer': [('ctle', 2), ('ptrim', 2)], 'vthdac': [('slicer', 2)], 'detect': [('pad_hs_rx', 1), ('pad_usb', 1)], 'wmon_sel': [('ctle', 1)],
 'ptrim': [('slicer', 2), ('wrx_cap', 2)], 'ptrim_output_stage': [('ptrim', 5)], 'wrx_cap': [('slicer', 3), ('pad_hs_rx', 1), ('digital', 0.5)],
 'r8arch_slicer_b': [('ctle', 2), ('ptrim', 2)], 'r8arch_capture_b': [('r8arch_slicer_b', 2), ('wrx_cap', 2)], 'r8arch_blend_pd8': [('r8arch_slicer_b', 3)],
 
 'wiredtx': [('pad_wire_tx', 3), ('digital', 0.5)], 'wtx_mux8': [('pad_wire_tx', 5)], 'wtx_ser8d': [('wtx_mux8', 4), ('wiredtx', 2), ('pll_tx', 1)], 'attached_tx_interlock': [('pad_wire_tx', 3)], 'term_buffer': [('pad_wire_tx', 3)],
 'txpad_bias': [('term_buffer', 3)], 'usb_txdrv': [('wiredtx', 3), ('pad_usb', 3)], 'hsbias': [('usb_txdrv', 3)], 'wtx_fallback_control': [('wiredtx', 2)],
 'ctle_follower_x2': [('ctle', 5)], 'isw_conv': [('adc_i', 1), ('adc_q', 1)], 'vcm_buffer': [('refbuf', 3)], 'agnd_tie': [('lna', 3)],
 'clk_obs': [('clockmux', 1)], 'bias_ext': [('core_bias', 3)], 'fwd_clk_repeaters': [('rx_aux_clk', 2)], 'atb0_pad': [('digital', 1)], 'atb1_pad': [('digital', 1)],
}
for i in range(6): T[f'steer_{i}'] = [('pad_wire_tx', 3)]
# region anchors (x, y) per chip: where a group goes before its partners exist; supply pads (G4: island -> (edge, coordinate of
# the supply bond along that edge), bond_map.txt sites at analog/pads/generated/provider-sites.json bond centres)
if CHIP == 'rf':     # RF chain on the west (RF_RX inputs[9/8], RF_TX inputs[1/0]); external-LO / REF pads on the east (bidir[20..24])
    ANCH = {'rf_rx': (1150, 1950), 'conv': (1700, 1300), 'lo': (2500, 2900), 'lod': (2300, 2600), 'rf_tx': (1100, 4100), 'pll': (3000, 1600),
            'debug': (2600, 3800), 'core': (2000, 2400)}
    ANCH_B = {'adc_i': (1650, 1250), 'adc_q': (2200, 1250), 'bbfilter_i': (1350, 1500), 'bbfilter_q': (1350, 2400), 'dac_i': (1500, 3700),
              'dac_q': (1500, 3300), 'core_bias': (2100, 2300), 'qvco': (2450, 2900), 'lo_ext': (2700, 3050), 'lo_vreg': (2950, 2400)}
    G4 = {'rf_rx': ('W', 2666.5), 'rf_tx': ('W', 3510.5), 'lod': ('E', 2033.5), 'lo': ('E', 2033.5), 'conv': ('W', 978.5), 'pll': ('E', 4143.5),
          'debug': ('E', 556.5)}
else:                # HS RX, USB, WIRE_TX, WTX_EXT on the east (bidir[14..24]); REF / AUX, WMON, TLP on the west
    ANCH = {'wired_rx': (2700, 1000), 'wired_cap': (2400, 1000), 'wired_tx': (2600, 2600), 'pll': (2200, 1500), 'debug': (1200, 3000),
            'core': (1800, 2300)}
    ANCH_B = {'core_bias': (1800, 2300), 'wrx_cap': (2400, 700), 'r8arch_capture_b': (2300, 1000), 'pll_cdr': (2100, 1300)}
    G4 = {'wired_cap': ('E', 556.5), 'wired_rx': ('E', 2260.0),   # wired_rx switch beside dvdd_pads[1] (PDS-9)
           'wired_tx': ('E', 2244.5), 'pll': ('E', 4143.5), 'debug': ('W', 2666.5)}
# keep-away rules (v6 list, unchanged): aggressor, victim, um
RULES = [('digital', 'adc_i', 210), ('digital', 'adc_q', 210), ('digital', 'core_bias', 100), ('digital', 'bbfilter_i', 100), ('digital', 'bbfilter_q', 100),
         ('digital', 'lna', 1000), ('digital', 'qvco', 300), ('wrx_cap', 'adc_i', 200), ('wrx_cap', 'adc_q', 200), ('r8arch_capture_b', 'adc_i', 200),
         ('r8arch_capture_b', 'adc_q', 200), ('pll_cdr', 'qvco', 500), ('pll_tx', 'qvco', 500), ('pll_cdr', 'adc_i', 200), ('pll_cdr', 'bbfilter_i', 200),
         ('aosc', 'lna', 300), ('aosc', 'por', 300), ('aosc', 'adc_q', 300), ('rfdriver', 'core_bias', 340), ('rfdriver', 'adc_i', 839), ('rfdriver', 'lna', 1000),
         ('wiredtx', 'adc_i', 97), ('qvco', 'lna', 250),
         # INT23 QVCO placement rule (integration-m23.md path 1): spiral centres >= 1.7 mm from the west die edge and >= 1.0 mm
         # along the edge from the RF_TX pads. Applied to the cell edge (spiral centres are about 200 um inside it):
         # 1500 um / 800 um against virtual rectangles.
         ('west_edge', 'qvco', 1500), ('rf_tx_band', 'qvco', 800)]
RULES += [tuple(r) for r in json.loads(os.environ.get('KEEPAWAY', '[]'))]     # assembly: extra keep-aways
ADJ = {}
for a_, b_, d_, w_ in json.loads(os.environ.get('ADJ', '[]')):   # assembly: [block, partner, max gap um, weight]
    ADJ.setdefault(a_, []).append((b_, d_, w_))
KA = {}
for a, v, d in RULES:
    KA.setdefault(a, []).append((v, d)); KA.setdefault(v, []).append((a, d))

TIER1 = ['qvco', 'lo_mmd', 'lo_vreg', 'lna', 'lna_ind_p', 'lna_ind_n', 'lna_deg_p', 'lna_deg_n', 'rxmix_i', 'rxmix_q', 'rfdriver', 'txmix_i', 'txmix_q',
         'ctle', 'slicer', 'ptrim', 'ptrim_output_stage', 'wrx_cap', 'r8arch_slicer_b', 'r8arch_capture_b', 'pll_cdr', 'cdr', 'wtx_mux8', 'wtx_ser8d', 'wiredtx', 'pll_tx',
         'usb_txdrv', 'lo_ext', 'termination', 'term_buffer', 'attached_tx_interlock', 'rx_ref_in', 'rx_aux_clk', 'rx_wtx_ext', 'pll_vreg2']

# ---- fixed geometry --------------------------------------------------------------------------------------------------------
SITES = json.load(open(f'{P_}/analog/pads/generated/provider-sites.json'))['sites']
BOND = [l.split()[:4] for l in open(f'{P_}/integration/chips/{CHIP}/bond_map.txt') if l.strip() and not l.startswith('#')]
# custom pad families: width along the edge (um) and depth from the die edge (cell drawn from 26 um); measured cells (ledger)
FAM = {'pad_rf_pair': (310.06, 912.9), 'pad_rftxpad': (310.06, 912.9), 'pad_refpad': (401.2, 912.9), 'pad_hspad': (492.0, 912.9),
       'pad_wirepad': (521.2, 914.9), 'pad_txpad': (481.2, 914.9), 'pad_single_leg': (205.0, 912.9)}
# offset of each family's cell centre from the midpoint of its sites, along the edge (the bond openings are not centred in
# the cell; measured as the snap of the former skeleton build, 2026-11-19; the assembly flow passes the real footprints)
OFS = {'pad_rf_pair': 11.945, 'pad_rftxpad': 11.945, 'pad_refpad': 60.38, 'pad_hspad': 102.945, 'pad_wirepad': -90.62,
       'pad_txpad': 100.38, 'pad_single_leg': -97.455}
def pads():
    """custom pad rectangles of this chip, centred on the bond centres of their sites (bond_map.txt); PADS_JSON (assembly
    flow): the footprints of the real pad cells as placed on the template openings, used as they are"""
    if os.environ.get('PADS_JSON'):
        return {n: [tuple(r) for r in rs] for n, rs in json.load(open(os.environ['PADS_JSON'])).items()}
    MASTER = {r['item']: r['master'] for r in L['rows']}
    by = {}
    for site, side, net, inst in BOND:
        if MASTER.get(inst) in FAM: by.setdefault(inst, []).append(SITES[site]['bond_center_um'][1])
    P = {}
    for n, ys in by.items():
        m = MASTER[n]; w, d = FAM[m]
        if m == 'pad_single_leg' and SCEN == 'S': w = 302.2
        mid = sum(ys)/len(ys)+OFS[m]; side = next(r[1] for r in BOND if r[3] == n)
        x0, x1 = (26.0, 26.0+d) if side == 'west' else (3906.0-d, 3906.0)
        P[n] = [(x0, mid-w/2, x1, mid+w/2)]
        if m == 'pad_hspad': P[n].append((x0 if side == 'west' else 3480.0, mid+w/2, x1 if side == 'west' else x1-d+487.0, mid+w/2+32.0))
        if m == 'pad_wirepad':          # attachment column, inboard of the first site
            col = 522.6 if SCEN == 'S' else 300.0
            P[n].append((x0-col, mid-w/2, x0, mid-w/2+189.7) if side == 'east' else (x1, mid-w/2, x1+col, mid-w/2+189.7))
        if m == 'pad_txpad':
            col = 311.82 if SCEN == 'S' else 160.0
            P[n].append((x0-col, mid+w/2-141.4, x0, mid+w/2) if side == 'east' else (x1, mid+w/2-141.4, x1+col, mid+w/2))
    for n in (NOPAD | ({'pad_bb_i', 'pad_bb_q', 'pad_wmon'} if SCEN == 'LB' else set())): P.pop(n, None)
    return P

def run(mw, mx0, rng=None, strat=0):
    p = Packer(CORE, G=2.0); mh = round(MACRO_A/mw, 1)
    for n, rs in pads().items():
        p.fixed(n, rs)
    dig = (mx0, CORE[3]-mh, mx0+mw, CORE[3]); p.fixed('digital', [dig], halo=HALO)
    P_ = pads()
    p.rects['west_edge'] = (0.0, -1e6, 0.0, 1e6)
    if 'pad_rf_tx' in P_: p.rects['rf_tx_band'] = (-1e6, P_['pad_rf_tx'][0][1], 1e6, P_['pad_rf_tx'][0][3])
    fixed = {'digital': dig}
    rsv = {'d2h_strip': (1387.7, CORE[1], 2700.0, CORE[1]+24.0)}
    if CHIP == 'wired': rsv['wtx_tcoil_rsv'] = (2900.0, 2922.0, 3470.0, 3042.0)
    if CHIP == 'rf' and 'pad_ref' in P_:      # external-LO legs from the east REF / AUX pads to lo_ext
        rsv['lo_legs_rsv'] = (P_['pad_ref'][0][0]-49.0, P_['pad_ref'][0][1], P_['pad_ref'][0][0], P_['pad_aux_clk'][0][3])
    # assembly routing channels (CHANNEL um, 0 = none): a strip under the macro's south edge and east of it, kept free of
    # blocks and decap so the macro's pins reach the core
    CH = float(os.environ.get('CHANNEL', '0'))
    if CH > 0:
        rsv['chan_macro_s'] = (dig[0], dig[1]-HALO-CH, dig[2], dig[1]-HALO)
        rsv['chan_macro_e'] = (dig[2]+HALO, dig[1]-HALO-CH, min(dig[2]+HALO+CH, CORE[2]), CORE[3])
        rsv['chan_macro_w'] = (max(dig[0]-HALO-CH, CORE[0]), dig[1]-HALO-CH, dig[0]-HALO, CORE[3])
    # assembly: keep the pocket east of the macro free of blocks (POCKET=1): on pt_wired it is walled off by the macro and
    # pad_wire_tx, so blocks there pull their nets through the corner gap
    if os.environ.get('POCKET') == '1':
        rsv['pocket_e'] = (dig[2]+HALO, dig[1]-HALO, CORE[2], CORE[3])
    for n_, r_ in json.loads(os.environ.get('EXTRA_RSV', '{}')).items():   # assembly: slots of blocks it places itself
        rsv[n_] = tuple(r_)
    if CORRIDOR:
        cx = min(max(2281.2, dig[0]+100), dig[2]-150)
        rsv['corridor_s_rsv'] = (cx, CORE[1]+34.0, cx+46.5, dig[1]-HALO)
    for n, r in rsv.items():
        p.fixed(n, [r], halo=(HALO if n != 'd2h_strip' else 0)); fixed[n] = r
    order = []
    isw = [n for n in blocks if n.startswith('isw_')]
    order += sorted(isw, key=lambda n: -blocks[n]['w']*blocks[n]['h'])
    order += [n for n in blocks if n.startswith('decap_bank')]
    # ordering strategies (the search tries all three, then jittered repeats):
    #   0 = area-descending only; 1 = giants (>= 0.19 mm2) first, then the flow list, then by area; 2 = flow list first, then by area.
    # flow list (TIER1) = blocks pinned to a pad, a spiral or a chain head, in signal-flow order
    if strat == 1:
        order += sorted([n for n in blocks if n not in order and blocks[n]['w']*blocks[n]['h'] >= 1.9e5], key=lambda n: -blocks[n]['w']*blocks[n]['h'])
    if strat >= 1:
        order += [n for n in TIER1 if n in blocks and n not in order]
    rest = [n for n in blocks if n not in order and not n.startswith('decap_tile')]
    jit = {n: (1.0 if rng is None else math.exp(rng.normal(0, 0.35))) for n in rest}
    order += sorted(rest, key=lambda n: -blocks[n]['w']*blocks[n]['h']*jit[n])
    order += [n for n in blocks if n.startswith('decap_tile')]      # tiles last: they take the holes the blocks leave
    big = [n for n in order if blocks[n]['w']*blocks[n]['h'] > 3e4 and not n.startswith(('decap', 'isw', 'char'))]
    li = 0
    for n in order:
        b = blocks[n]; tg = list(T.get(n, [])); mg = []; ring = None; g = b['grp']
        anchor = ANCH_B.get(n) or ANCH.get(g, ANCH['core']); aw = 0.25
        if n.startswith('isw_'):
            isl = n[4:]
            if isl in G4: ring = (G4[isl][0], G4[isl][1], 150.0-0.0, 600.0)
            else: ring = None
            anchor = ANCH.get(isl, ANCH['core']); aw = 0.05
        elif n.startswith('decap_bank'):
            tg = [('digital', 5)]; mg = [('digital', 125.0)]; aw = 0.0
        elif b['master'].startswith('atb_leaf') or b['master'].startswith('iso_'):
            tg = [(big[li % len(big)], 1.0)]; li += 1; aw = 0.02
        elif n.startswith(('char', 'decap_tile')) or n in ('por', 'aosc', 'ring_osc', 'vco_replica') or n.startswith('obs_pre4'):
            aw = 0.02                           # no flow partner: take any hole (pure compaction)
        if b['mA'] > 0 and f'isw_{g}' in blocks and not n.startswith('isw_'):
            tg.append((f'isw_{g}', ISLW*b['mA']))    # supply flow: every island block is pulled to its switch in proportion to its current (G5/G6 strap)
        if b['mA'] > 20.0 and f'isw_{g}' in blocks:
            mg.append((f'isw_{g}', 500.0))      # power-delivery.md G6: blocks above 20 mA within ~500 um of their switch
        for t_, d_, w_ in ADJ.get(n, []):           # assembly adjacency (signal-flow distances, relaxable)
            tg.append((t_, w_)); mg.append((t_, d_))
        p.place(n, b['w'], b['h'], halo=b['halo'], rot=b['rot'], targets=tg, anchor=(anchor[0], anchor[1], aw),
                keepaway=KA.get(n, []), maxgap=mg, ring=ring, lam=0.6, step=2)
    return p, fixed, dig

t0 = time.time(); best = None; trials = []
rng0 = np.random.default_rng(SEED)
for (mw, mx0, tr) in [(a, b, t) for (a, b) in MACROS for t in range(TRIES)]:
    st = int(os.environ['STRAT']) if 'STRAT' in os.environ else tr % 3   # STRAT forces one ordering strategy
    p, fixed, dig = run(mw, mx0, None if tr < 3 else rng0, st)
    pa = sum(blocks[n]['w']*blocks[n]['h'] for n in p.placed); ua = sum(blocks[n]['w']*blocks[n]['h'] for n, _ in p.unplaced)
    trials.append(dict(strategy=st, macro_w=mw, macro_h=round(MACRO_A/mw, 1), macro_x0=mx0, placed=len(p.placed), unplaced=len(p.unplaced),
                       unplaced_mm2=round(ua/1e6, 4), relaxed=len(p.relaxed), free_mm2=round(p.free_area()/1e6, 4)))
    flow = sum(w_*(max(p.rects[t_][0]-p.rects[n_][2], p.rects[n_][0]-p.rects[t_][2], 0)+max(p.rects[t_][1]-p.rects[n_][3], p.rects[n_][1]-p.rects[t_][3], 0))
               for n_ in p.placed for t_, w_ in T.get(n_, []) if t_ in p.rects)
    flow += sum(0.05*blocks[n_]['mA']*(max(p.rects[sw_][0]-p.rects[n_][2], p.rects[n_][0]-p.rects[sw_][2], 0)+max(p.rects[sw_][1]-p.rects[n_][3], p.rects[n_][1]-p.rects[sw_][3], 0))
                for n_ in p.placed for sw_ in ['isw_'+blocks[n_]['grp']] if sw_ in p.rects and n_ != sw_)
    trials[-1]['flow_cost_mm'] = round(flow/1e3, 1)
    key = (round(ua/4e4), len(p.relaxed), round(flow/2e4), ua)
    if best is None or key < best[0]:
        best = (key, p, fixed, dig, mw, mx0)
    print(trials[-1], f'{time.time()-t0:.0f}s', flush=True)
_, p, fixed, dig, mw, mx0 = best
assert not overlap_check(p), overlap_check(p)[:5]

# ---- report -----------------------------------------------------------------------------------------------------------------
def gap(r1, r2):
    return math.hypot(max(r2[0]-r1[2], r1[0]-r2[2], 0.0), max(r2[1]-r1[3], r1[1]-r2[3], 0.0))
def mgap(r1, r2):
    return max(r2[0]-r1[2], r1[0]-r2[2], 0.0)+max(r2[1]-r1[3], r1[1]-r2[3], 0.0)
rects = dict(p.rects)
audit = [dict(aggressor=a, victim=v, min_um=d, gap_um=round(gap(rects[a], rects[v]), 1), ok=gap(rects[a], rects[v]) >= d)
         for a, v, d in RULES if a in rects and v in rects]
for k_ in ('west_edge', 'rf_tx_band'): rects.pop(k_, None)
core_a = (CORE[2]-CORE[0])*(CORE[3]-CORE[1])
blk_a = sum(b['w']*b['h'] for b in blocks.values()); plc_a = sum(blocks[n]['w']*blocks[n]['h'] for n in p.placed)
unp = [(n, why, round(blocks[n]['w']*blocks[n]['h'])) for n, why in p.unplaced]
halo_a = sum((blocks[n]['w']+2*blocks[n]['halo'])*(blocks[n]['h']+2*blocks[n]['halo'])-blocks[n]['w']*blocks[n]['h'] for n in p.placed)
free_a = p.free_area()
# scrap: free area that cannot take even a 60 x 60 um block with its halo (erosion by an 80 x 80 window)
K = p.K; occ = p.occ[K:K+p.ny, K:K+p.nx]; S = np.zeros((p.ny+1, p.nx+1), dtype=np.int32); S[1:, 1:] = occ.astype(np.int32).cumsum(0).cumsum(1)
def usable(win):
    c = int(win/p.G); F = S[c:, c:]-S[:-c, c:]-S[c:, :-c]+S[:-c, :-c]; ok = (F == 0)
    u = np.zeros_like(occ, dtype=np.int32)       # dilate back: mark every cell covered by a free window
    d = np.zeros((p.ny+1, p.nx+1), dtype=np.int32); jj, ii = np.nonzero(ok)
    np.add.at(d, (jj, ii), 1); np.add.at(d, (jj+c, ii), -1); np.add.at(d, (jj, ii+c), -1); np.add.at(d, (jj+c, ii+c), 1)
    u = d.cumsum(0).cumsum(1)[:p.ny, :p.nx] > 0
    return float(u.sum())*p.G*p.G
use80 = usable(80.0); use200 = usable(200.0)
# supply: island strap need (power-delivery.md G6: Metal5 width >= 0.47 um per mA per 100 um)
straps = []; strap_area = 0.0
for n in p.placed:
    b = blocks[n]; sw = f"isw_{b['grp']}"
    if b['mA'] > 0 and sw in rects and n != sw:
        d = mgap(rects[n], rects[sw]); wdt = 0.47*b['mA']*max(d, 50.0)/100.0
        straps.append(dict(block=n, island=b['grp'], mA=b['mA'], dist_um=round(d), m5_width_um=round(wdt, 1))); strap_area += wdt*max(d, 50.0)
sw_ring = []
for n in p.placed:
    if n.startswith('isw_') and n[4:] in G4:
        e, c = G4[n[4:]]; r = rects[n]
        eg = {'W': r[0]-CORE[0], 'E': CORE[2]-r[2], 'S': r[1]-CORE[1], 'N': CORE[3]-r[3]}
        sw_ring.append(dict(switch=n, pad_edge=e, pad_coord=c, rect=[round(v) for v in r], edge_gaps={k: round(v) for k, v in eg.items()}))
# routing demand from the placement: macro <-> block signal counts x Manhattan distance (edge to edge)
route = []; wire_um = 0.0
for n in p.placed:
    b = blocks[n]
    if b['nets'] > 0:
        d = mgap(rects[n], dig); route.append((n, b['nets'], round(d))); wire_um += b['nets']*d
report = dict(scenario=SCEN, ring_um=RING, grow_um=GROW, nopad=sorted(NOPAD), tries=TRIES, halo_um=HALO, bank=BANK, corridor=CORRIDOR, dropped=sorted(DROP), macro=dict(w=mw, h=round(MACRO_A/mw, 1), x0=mx0), trials=trials,
              core_mm2=round(core_a/1e6, 3), blocks=len(blocks), block_demand_mm2=round(blk_a/1e6, 3),
              placed=len(p.placed), placed_mm2=round(plc_a/1e6, 3), unplaced=unp, unplaced_mm2=round(sum(u[2] for u in unp)/1e6, 3),
              relaxed=p.relaxed, halo_area_mm2=round(halo_a/1e6, 3), free_after_mm2=round(free_a/1e6, 3),
              free_usable_80um_mm2=round(use80/1e6, 3), free_usable_200um_mm2=round(use200/1e6, 3), scrap_lt80um_mm2=round((free_a-use80)/1e6, 3),
              rule_audit=audit, rule_fails=[a for a in audit if not a['ok']], switches=sw_ring,
              straps=sorted(straps, key=lambda s: -s['m5_width_um'])[:25], strap_m5_area_mm2=round(strap_area/1e6, 3),
              macro_signal_wire_mm=round(wire_um/1e3, 1), route_top=sorted(route, key=lambda t: -t[1]*t[2])[:15],
              fixed={k: [round(v, 1) for v in r] for k, r in fixed.items()}, pads={k: [[round(v, 1) for v in r] for r in rs] for k, rs in pads().items()},
              placed_rects={n: dict(rect=[round(v, 1) for v in d['rect']], rot=d['rot'], grp=blocks[n]['grp']) for n, d in p.placed.items()})
RUN = os.environ.get('RUNDIR', f'{HERE}/run/{CHIP}'); os.makedirs(RUN, exist_ok=True)
report['chip'] = CHIP
json.dump(report, open(f'{RUN}/fit-{TAG}.json', 'w'), indent=0)
print(json.dumps({k: v for k, v in report.items() if k not in ('placed_rects', 'rule_audit', 'pads', 'fixed', 'trials', 'straps', 'route_top')}, indent=0)[:3500])

# ---- render ------------------------------------------------------------------------------------------------------------------
Sx = 0.25; PANEL = 560; Wpx, Hpx = int(DIE[2]*Sx)+PANEL, int(DIE[3]*Sx)+60
im = Image.new('RGB', (Wpx, Hpx), 'white'); d = ImageDraw.Draw(im)
try:
    F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
    FT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
except Exception:
    F = FB = FT = ImageFont.load_default()
def P(x, y): return (x*Sx, (DIE[3]-y)*Sx+50)
def box(r, fill, outline, w=1):
    a, b = P(r[0], r[3]), P(r[2], r[1]); d.rectangle([a, b], fill=fill, outline=outline, width=w)
COL = dict(rf_rx=('#f6d5d5', '#b03030'), rf_tx=('#f9c9c0', '#a03020'), conv=('#ead9f2', '#7a3a9a'), lo=('#fde6c8', '#c06000'), lod=('#fbd9a8', '#b05800'),
           pll=('#fff1c4', '#a07800'), wired_rx=('#d6efdc', '#2a7a40'), wired_cap=('#c2e8cc', '#1f6a34'), wired_tx=('#d0ecd0', '#3a7a2a'),
           core=('#dde7f5', '#2a5aa0'), debug=('#d4eef0', '#207080'))
box(DIE, '#f4f4ee', '#555', 2); box(CORE, '#ffffff', '#999', 1)
for n, rs in pads().items():
    for r in rs: box(r, '#d9d9d9', '#666')
    r = rs[0]; c = P(r[0]+6, r[3]-6); d.text(c, n, fill='#333', font=F)
box(dig, '#e9f27a', '#2040a0', 3); c = P((dig[0]+dig[2])/2, (dig[1]+dig[3])/2)
d.text((c[0]-110, c[1]-22), 'DIGITAL MACRO', fill='#2040a0', font=FT); d.text((c[0]-110, c[1]+6), f'{mw:.0f} x {MACRO_A/mw:.0f} um = {MACRO_A/1e6:.3f} mm2', fill='#2040a0', font=FB)
for n, r in fixed.items():
    if n != 'digital': box(r, '#eeeeee', '#888')
for n, pl in p.placed.items():
    r = pl['rect']; b = blocks[n]
    if n.startswith(('decap_bank', 'decap_tile')): box(r, '#c9dcf2', '#8aa8d0'); continue
    f, o = COL.get(b['grp'], ('#eee', '#444'))
    if n.startswith('isw_'): f, o = '#404040', '#000'
    if n.startswith(('r8arch', 'wtx_ser8d', 'wtx_mux8')) or ROW.get(n, {}).get('est'): o = '#d000d0'
    box(r, f, o, 2 if o == '#d000d0' else 1)
    wpx, hpx = (r[2]-r[0])*Sx, (r[3]-r[1])*Sx
    if wpx > 34 and hpx > 12:
        lab = n if wpx > 7*len(n) else n[:max(3, int(wpx/7))]
        d.text((P(r[0], r[3])[0]+3, P(r[0], r[3])[1]+2), lab, fill=('#fff' if n.startswith('isw_') else '#000'), font=F)
x0 = int(DIE[2]*Sx)+14; y = 56
def line(t, f=F, col='#000'):
    global y
    d.text((x0, y), t, fill=col, font=f); y += 16 if f is F else 20
d.text((10, 12), f'pt_{CHIP} die-fit scenario {SCEN}: {dict(S="as built (newest layout on disk)", T="all targets met", LB="every block at its lower bound")[SCEN]}  (tag {TAG}, halo {HALO:.0f} um)', fill='#000', font=FT)
line(f'core {CORE[2]-CORE[0]:.0f} x {CORE[3]-CORE[1]:.0f} = {core_a/1e6:.3f} mm2', FB)
line(f'blocks to place: {len(blocks)}  ({blk_a/1e6:.3f} mm2)')
line(f'placed: {len(p.placed)}  ({plc_a/1e6:.3f} mm2)', FB, '#006000')
line(f'UNPLACED: {len(unp)}  ({sum(u[2] for u in unp)/1e6:.3f} mm2)', FB, '#c00000' if unp else '#006000')
for n, why, a in sorted(unp, key=lambda u: -u[2])[:26]:
    line(f'  {n}  {a/1e6:.3f}', F, '#c00000')
if len(unp) > 26: line(f'  ... and {len(unp)-26} more', F, '#c00000')
line(f'free after placement: {free_a/1e6:.3f} mm2', FB)
line(f'  usable by a >=60 um block: {use80/1e6:.3f}')
line(f'  usable by a >=180 um block: {use200/1e6:.3f}')
line(f'  scrap (slivers < 80 um): {(free_a-use80)/1e6:.3f}')
line(f'halo (channels) inside placed: {halo_a/1e6:.3f} mm2')
line(f'relaxed constraints: {len(p.relaxed)}', FB, '#a05000')
for n, why in p.relaxed[:14]:
    line(f'  {n}: {why[:44]}', F, '#a05000')
line(f'keep-away rule fails: {len(report["rule_fails"])}', FB)
line('legend: black = island switch, blue tiles = decap bank,', F); line('magenta outline = estimate or reserve (not a measured layout)', F)
im.save(f'{RUN}/fit-{TAG}.png')
print('wrote', f'{RUN}/fit-{TAG}.png', f'{time.time()-t0:.0f}s')
