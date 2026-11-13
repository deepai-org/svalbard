"""Floorplan v6 (2026-11-13): outline-level assembly of the current published blocks.

Inputs: bbox.json (outlines measured from the current GDS in the pinned KLayout image by bbox.py),
v5 run2 floorplan.json (pad-family footprints, die/core, reserves), v5 abstracts (unchanged masters),
v5 digital.json (macro pin groups for the congestion estimate).
Outputs (run/): floorplan-v6.json, report-v6.json, chip-assembly-v6.png.
Not a GDS assembly: no routing, no DRC. Blocks are placed as rectangles with a 10 um halo on a 2 um grid.
"""
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = '/home/ubuntu/svalbard/scratch/chip-assembly-v6'
OUT = '/home/ubuntu/svalbard/scratch/area-pass-4'
import os
SCEN = int(os.environ.get('SCEN', '0'))
V5 = '/home/ubuntu/svalbard/scratch/chip-assembly-v5/run2'
DIE = (0.0, 0.0, 3932.0, 5122.0)
CORE = (452.0, 452.0, 3480.0, 4670.0)   # block area (v5 CORE 442..3490/4680 minus the 10 um ring halo)
G = 2.0
HALO = 10.0

bb = {k.split(':')[1]: v for k, v in json.load(open(f'{HERE}/bbox.json')).items()}
ab5 = {k: v['bbox'] for k, v in json.load(open(f'{V5}/abstracts.json')).items()}
fp5 = json.load(open(f'{V5}/floorplan.json'))
dig5 = json.load(open(f'{V5}/digital.json'))


def dims(top=None, v5=None):
    b = bb[top] if top else ab5[v5]
    return (b[2]-b[0], b[3]-b[1])


# ---------------------------------------------------------------------------------------------------------------
# Inventory: name -> (w, h, group, seed (x, y) of centre, note). Sizes from the current GDS unless marked v5.
SQ = lambda a_mm2: (math.sqrt(a_mm2)*1e3, math.sqrt(a_mm2)*1e3)
INV = {}
def add(name, wh, grp, seed, note='', rot=True):
    INV[name] = dict(w=wh[0], h=wh[1], grp=grp, seed=seed, note=note, rot=rot)

# converters / RF RX chain (west half, south of the macro)
add('adc_i', dims('pt_adc_i'), 'conv', (2610, 1085), 'r? adc_i')
add('adc_q', dims('pt_adc_q'), 'conv', (2130, 1085), '')
add('bbfilter_i', dims('pt_bbfilter_i'), 'rf', (1600, 1700), 'FS-2')
add('bbfilter_q', dims('pt_bbfilter_q'), 'rf', (1600, 1100), 'FS-2')
add('lna', dims('pt_lna'), 'rf', (1010, 1520), 'RC-16i (src_p/src_n to downbond pads)')
add('lc_load_rsv', SQ(0.10), 'rf', (1150, 1250), 'RC-16j LC load spiral reserve 0.1 mm2')
add('rxmix_i', dims('pt_rxmix_i'), 'rf', (1080, 1800), '')
add('rxmix_q', dims('pt_rxmix_q'), 'rf', (1150, 1150), '')
add('refbuf', dims('pt_refbuf'), 'conv', (2300, 2000), '')
add('bb_tap_i', dims('pt_bb_tap'), 'rf', (1050, 2150), '')
add('bb_tap_q', dims('pt_bb_tap'), 'rf', (1050, 3500), '')
add('bb_tap_wmon', dims('pt_bb_tap'), 'debug', (3300, 3500), '')
# LO (west, between the RX chain and the TX chain)
add('qvco', dims('pt_lc_qvco5'), 'lo', (1400, 2400), 'QVCO r6b (LO20)')
add('lo_mmd', dims('pt_lo_mmd'), 'lo', (2050, 2000), '')
add('lo_mmd_qdum', dims('pt_lo_mmd_qdum'), 'lo', (1150, 2400), '')
add('lo_pfdcp', dims('pt_lo_pfdcp'), 'lo', (1150, 2800), 'LO19')
add('lo_lf', dims('pt_lo_lf'), 'lo', (1150, 3200), 'lo_lf r5 (LO20)')
add('lo_obs', dims('pt_lo_obs'), 'lo', (1100, 2950), '')
add('lo_ext', dims('pt_lo_ext'), 'lo', (1150, 3300), 'r4h')
add('polyphase', dims('pt_polyphase'), 'lo', (1050, 3800), '')
# RF TX (north-west, next to RF_TX pad at west y 4317-4627)
add('txmix_i', dims('pt_txmix_i'), 'rf', (1100, 3950), '')
add('txmix_q', dims('pt_txmix_q'), 'rf', (1100, 4050), '')
add('txsum', dims('pt_txsum'), 'rf', (1100, 4150), '')
add('rfdriver', dims('pt_rfdriver'), 'rf', (750, 4100), '')
add('dac_i', dims('pt_dac_i'), 'conv', (1100, 3700), '')
add('dac_q', dims('pt_dac_q'), 'conv', (1100, 3400), '')
# timing / rings (east, by the wired blocks; QVCO far away)
add('pll_cdr', dims('pt_pll_ring'), 'pll', (3150, 2450), 'r9w CDR ring')
add('pll_tx', dims('pt_pll_ring_core'), 'pll', (3300, 2900), 'r9w core (TX)')
add('pll_vreg2', dims('pt_pll_vreg2'), 'pll', (2900, 2500), 'PD36 one cell for both rings')
add('clockmux', dims('pt_clockmux'), 'pll', (2900, 2900), '')
add('prescale', dims('pt_prescale'), 'pll', (3300, 4300), '')
add('wordclk', dims('pt_wordclk'), 'pll', (2900, 3000), '')
add('clk_obs16', dims('pt_clk_obs16'), 'debug', (3300, 4100), '')
add('obs_pre4', dims('pt_obs_pre4'), 'debug', (3250, 4450), '')
add('ring_osc', dims('pt_ring_osc'), 'debug', (3300, 3800), '')
add('vco_replica', dims('pt_vco_replica'), 'debug', (3300, 3900), '')
add('aosc', dims('pt_aosc'), 'core', (3300, 4550), '')
add('rx_aux_clk', dims('pt_diff_clk_rx'), 'debug', (1050, 3150), '')
add('rx_wclk_in', dims('pt_diff_clk_rx'), 'debug', (2850, 1550), '')
add('rx_wtx_ext', dims('pt_diff_clk_rx'), 'debug', (2850, 3200), '')
# wired RX (east, south) + R8-ARCH reserve
add('wrx_cap', dims('pt_wrx_cap'), 'wired', (2050, 2700), 'r7 without gearbox (W7-GEAR)')
add('slicer', dims('pt_slicer'), 'wired', (2700, 1500), '')
add('ctle', dims('pt_ctle'), 'wired', (2600, 900), '')
add('cdr', dims('pt_cdr'), 'wired', (2900, 1900), '')
add('ptrim', dims('pt_ptrim'), 'wired', (3150, 1900), '')
add('vthdac', dims('pt_vthdac'), 'wired', (2700, 1350), '')
add('detect', dims('pt_detect'), 'wired', (3200, 600), '')
add('termination', dims('pt_termination'), 'wired', (2450, 600), '')
add('rxlevel', dims('pt_rxlevel'), 'wired', (2750, 520), '')
add('rxselect', dims('pt_rxselect'), 'wired', (2800, 1300), '')
add('wmon_sel', dims('pt_wmon_sel'), 'wired', (2900, 520), '')
add('r8arch_rsv', SQ(0.43), 'wired', (2700, 1700), 'R8-ARCH reserve 0.43 mm2 (slicer B, capture B, blenders, PD8)')
# wired TX
add('wiredtx', dims('pt_wiredtx'), 'wired', (2900, 2800), '')
add('tx8_rsv', (450.0, 445.0), 'wired', (2900, 2800), 'TX eighth-rate core growth (serq8 0.325 - serq4c 0.158) + 2 CML pre-drivers 0.028')
add('hsbias', dims('pt_wtx_hsbias'), 'wired', (2900, 2400), '')
add('wtx_fallback_control', dims('pt_wtx_fallback_control'), 'wired', (3100, 2400), '')
add('term_buffer', dims('buffer_compensated_flat'), 'wired', (3250, 2600), 'PD46b 156.8 x 479.6')
add('attached_tx_interlock', dims(v5='attached_tx_interlock'), 'wired', (3250, 2300), 'v5 outline')
for i in range(6):
    add(f'steer_{i}', dims('tx_steering_buffer_flat'), 'wired', (3300, 2450+40*i), 'PD46 compact')
# core infrastructure
add('core_bias', dims(v5='core_bias'), 'core', (925, 625), 'v5 outline (P4 compact)')
add('por', dims(v5='por'), 'core', (600, 900), '')
for n, s in dict(wired=(3150, 1500), rf=(1300, 2150), pll=(3050, 2150), conv=(1700, 600), debug=(3250, 3600)).items():
    add(f'isw_{n}', dims(v5=f'isw_{n}'), n if n != 'debug' else 'debug', s, '')
add('atb0_pad', dims(v5='atb_pad'), 'core', (1650, 2950), '')
add('atb1_pad', dims(v5='atb_pad'), 'core', (650, 2950), '')
for i, s in enumerate([(2450, 1700), (1250, 900), (3000, 1700), (1600, 2950), (3000, 1300), (650, 2850), (1100, 900)]):
    add(f'atb_grp{i}', dims(v5='atb_grp'), 'core', s, '')
# ATB leaves: 20 fast + 57 slow (v5 counts), seeded next to their island
LEAF_SEEDS = [(2800, 1600), (2450, 2100), (950, 1300), (1150, 900), (1550, 2950), (1100, 3600), (3100, 1300), (3000, 2350)]
for i in range(20):
    add(f'leaf_f{i}', dims(v5='atb_leaf_f'), 'core', LEAF_SEEDS[i % 8], '', rot=False)
for i in range(57):
    add(f'leaf_s{i}', dims(v5='atb_leaf_s'), 'core', LEAF_SEEDS[(i+3) % 8], '', rot=False)


# ---- area pass 4 scenarios (outline targets; SCEN 0 = v6 as published) ----------------------------------------
def retarget(n, a_mm2, shape=None):
    it = INV[n]
    if shape:
        it['w'], it['h'] = shape; return
    k = math.sqrt(a_mm2*1e6/(it['w']*it['h'])); it['w'] *= k; it['h'] *= k
TARGETS = {}
if SCEN >= 1:   # in hand: wrx_cap r7 compact (scratch, clean, q625 0/200), R8 capture B on the same master
    TARGETS['wrx_cap'] = (None, (1199.0, 242.0))
if SCEN >= 2:   # assigned repacks (>= ~0.4 device+2um utilisation; spirals untouched)
    for n, a in dict(adc_i=0.33, adc_q=0.33, lo_mmd=0.16, ptrim=0.10, bbfilter_i=0.23, bbfilter_q=0.23, cdr=0.09,
                     detect=0.09, dac_i=0.13, dac_q=0.13, pll_cdr=0.115, lo_ext=0.12, clk_obs16=0.065, pll_tx=0.065,
                     ctle=0.095, term_buffer=0.045).items():
        TARGETS[n] = (a, None)
for n, (a, sh) in TARGETS.items():
    retarget(n, a, sh)

# placement order: big first, then by area
ORDER = sorted(INV, key=lambda n: -(INV[n]['w']*INV[n]['h']))
FIRST = ['core_bias', 'adc_q', 'adc_i', 'bbfilter_q', 'bbfilter_i', 'lna', 'qvco', 'wrx_cap', 'lo_mmd', 'lc_load_rsv',
         'rxmix_i', 'rxmix_q', 'rfdriver', 'dac_i', 'dac_q', 'pll_cdr', 'pll_tx', 'pll_vreg2', 'ptrim', 'wiredtx', 'cdr',
         'lo_lf', 'lo_pfdcp', 'lo_ext', 'detect', 'ctle', 'slicer']
LAST = ['r8arch_rsv', 'tx8_rsv']
ORDER = FIRST + [n for n in ORDER if n not in FIRST+LAST] + LAST
if os.environ.get('ORDERMODE') == 'area':
    ORDER = sorted(INV, key=lambda n: -(INV[n]['w']*INV[n]['h']))

# keep-away rules (aggressor, victim, min edge distance um, source)
RULES = [
    ('digital', 'adc_i', 210, 'SUB-01 floor (300 target)'), ('digital', 'adc_q', 210, 'SUB-01 floor (300 target)'),
    ('digital', 'core_bias', 100, 'SUB-02'), ('digital', 'bbfilter_i', 100, 'SUB-01/05'), ('digital', 'bbfilter_q', 100, 'SUB-01/05'),
    ('digital', 'lna', 1000, 'SUB-03'), ('digital', 'qvco', 300, 'LO-03 (assumed, supply/substrate)'),
    ('wrx_cap', 'adc_i', 200, 'SUB-05-like (capture is a 600-800 MHz switching block)'), ('wrx_cap', 'adc_q', 200, 'as above'),
    ('pll_cdr', 'qvco', 500, 'LO-02/LO-03 ring-to-QVCO (assumed)'), ('pll_tx', 'qvco', 500, 'as above'),
    ('pll_cdr', 'adc_i', 200, 'RA-9 analogue'), ('pll_cdr', 'bbfilter_i', 200, 'RA-9 analogue'),
    ('aosc', 'lna', 300, 'SUB-04'), ('aosc', 'por', 300, 'SUB-04'), ('aosc', 'adc_q', 300, 'SUB-04'),
    ('rfdriver', 'core_bias', 340, 'SUB-07/TH-01'), ('rfdriver', 'adc_i', 839, 'SUB-07'), ('rfdriver', 'lna', 1000, 'SUB-07'),
    ('wiredtx', 'adc_i', 97, 'SUB-08/RA-10'), ('qvco', 'lna', 250, 'LO self-mixing (assumed)'),
]
RULE_MAP = {}
for a, v, d, s in RULES:
    RULE_MAP.setdefault(a, []).append((v, d)); RULE_MAP.setdefault(v, []).append((a, d))


def gap(r1, r2):
    dx = max(r2[0]-r1[2], r1[0]-r2[2], 0.0); dy = max(r2[1]-r1[3], r1[1]-r2[3], 0.0)
    return math.hypot(dx, dy)


class Grid:
    def __init__(s):
        s.nx = int((CORE[2]-CORE[0])/G); s.ny = int((CORE[3]-CORE[1])/G)
        s.occ = np.zeros((s.ny, s.nx), dtype=np.uint8); s._sat = None
    def idx(s, r):
        return (max(0, int(math.floor((r[0]-CORE[0])/G))), max(0, int(math.floor((r[1]-CORE[1])/G))),
                min(s.nx, int(math.ceil((r[2]-CORE[0])/G))), min(s.ny, int(math.ceil((r[3]-CORE[1])/G))))
    def mark(s, r, v=1):
        i0, j0, i1, j1 = s.idx(r); s.occ[j0:j1, i0:i1] = v; s._sat = None
    def sat(s):
        if s._sat is None:
            s._sat = np.zeros((s.ny+1, s.nx+1), dtype=np.int32)
            s._sat[1:, 1:] = (s.occ > 0).astype(np.int32).cumsum(0).cumsum(1)
        return s._sat
    def free(s, r):
        if r[0] < CORE[0]-1e-6 or r[1] < CORE[1]-1e-6 or r[2] > CORE[2]+1e-6 or r[3] > CORE[3]+1e-6:
            return False
        i0, j0, i1, j1 = s.idx(r); S = s.sat()
        return S[j1, i1]-S[j0, i1]-S[j1, i0]+S[j0, i0] == 0


grid = Grid()
fixed, placed, failures = [], {}, []

# pads (v5 footprints; wirepad re-measured 1434.7 deep, was 1512.7) -----------------------------------------------
for f in fp5['fixed']:
    if f['name'] == 'pad_esd_test':
        continue  # PD35/PD48b: ESD_TEST dropped, TLP site 68 x 124 in-ring (below)
    r = list(f['rect'])
    if f['name'] == 'pad_usb':   # east, local y into core: shrink the core-side depth to the current outline
        r[0] = r[2]-1434.72-2.78
    kind = 'pad' if f['name'].startswith('pad_') else 'rsv'
    if f['name'] == 'digital':
        continue
    if f['name'] in ('rsv_isolation_band', 'rsv_lo_legs', 'rsv_corridor_s'):
        continue  # v5-specific; v6 enforces SUB-01 as a distance rule and the LO bundle is re-floorplanned
    fixed.append(dict(name=f['name'], rect=r, kind=kind))
# new in-ring pads (no core intrusion): TLP site at bidir[25], LNA source downbond pads beside RF_RX
fixed.append(dict(name='pad_tlp (bidir[25])', rect=[3906-124.3, 3684.0, 3906.0, 3752.0], kind='pad'))
fixed.append(dict(name='pad_lna_src_p', rect=[26.0, 1290.0, 150.0, 1358.0], kind='pad'))   # gap vss_pads[1] .. RF_RX
fixed.append(dict(name='pad_lna_src_n', rect=[26.0, 1695.0, 150.0, 1763.0], kind='pad'))   # gap RF_RX .. BB_I
# digital macro 1716 x 1640 (DT-4a), north edge, same x as v5
DW, DH = 1716.0, 1640.0
if SCEN >= 3: DH = round(2.45e6/DW, 1)   # digital 2.45 mm2 (buffer pct + 75 % util)
fixed.append(dict(name='digital', rect=[1262.0, 4670.0-DH, 1262.0+DW, 4670.0], kind='digital'))

# area pass 4: pad / reserve geometry
for f in fixed:
    if f['name'] == 'pad_hs_rx' and SCEN >= 1:      # PD-AP4 stacked hspad: 492 x 912.91 (was 478 x 1111.25)
        f['rect'] = [3906.0-912.91, 1227.055-492.0, 3906.0, 1227.055]
    if f['name'] == 'rsv_h2d_gearbox' and SCEN >= 1:  # X6: right-size to the D2H basis (0.031 mm2)
        f['rect'] = [2990.0, 4670.0-64.0, 3480.0, 4670.0]
    if f['name'] == 'pad_usb' and SCEN >= 3:        # wirepad attachment repack target: network depth + 300 um
        f['rect'][0] = 3906.0-912.91-300.0
    if f['name'] == 'pad_wire_tx' and SCEN >= 3:    # txpad attachment repack target: network depth + 160 um
        f['rect'][0] = 3906.0-912.91-160.0
if SCEN >= 3:
    for f in fixed:
        if f['kind'] == 'pad' and f['rect'][2]-f['rect'][0] > 900 and f['name'] not in ('pad_usb', 'pad_wire_tx', 'pad_hs_rx'):
            pass
for f in fixed:
    r = f['rect']
    grid.mark((r[0]-HALO, r[1]-HALO, r[2]+HALO, r[3]+HALO) if f['kind'] != 'pad' else r)
all_rects = {f['name']: f['rect'] for f in fixed}


def try_place(name):
    it = INV[name]; sx, sy = it['seed']
    halo = 4.0 if name.startswith('leaf') else HALO
    best = None
    shapes = [(it['w'], it['h'])] + ([(it['h'], it['w'])] if it['rot'] and abs(it['w']-it['h']) > 1 else [])
    step = 4.0 if it['w']*it['h'] < 5e3 else 10.0
    R = 0.0
    while R < 4500:
        n = max(8, int(2*math.pi*max(R, 1)/step))
        for k in range(n):
            cx, cy = sx+R*math.cos(2*math.pi*k/n), sy+R*math.sin(2*math.pi*k/n)
            for (w, h) in shapes:
                x0 = round((cx-w/2-CORE[0])/G)*G+CORE[0]; y0 = round((cy-h/2-CORE[1])/G)*G+CORE[1]
                r = (x0, y0, x0+w, y0+h)
                if not grid.free((r[0]-halo, r[1]-halo, r[2]+halo, r[3]+halo)):
                    continue
                ok = all(gap(r, all_rects[o]) >= d for o, d in RULE_MAP.get(name, []) if o in all_rects)
                if ok:
                    return r, (w != it['w'])
        R += step
    return None, None


for name in ORDER:
    r, rot = try_place(name)
    if r is None:
        failures.append(name); continue
    halo = 4.0 if name.startswith('leaf') else HALO
    grid.mark((r[0]-halo, r[1]-halo, r[2]+halo, r[3]+halo))
    placed[name] = dict(INV[name], rect=list(r), rot=rot); all_rects[name] = list(r)

# decap fill: stacked MOS tile (M1-M2, 2.33 fF/um2) under MIM m4m5 (2 fF/um2) in free 120 x 120 cells --------------
CELL = 120.0; decaps = []
free_area_before = float((grid.occ == 0).sum())*G*G
y = CORE[1]
while y+CELL <= CORE[3]:
    x = CORE[0]
    while x+CELL <= CORE[2]:
        r = (x, y, x+CELL, y+CELL)
        if grid.free((r[0]-6, r[1]-6, r[2]+6, r[3]+6)):
            decaps.append(r); grid.mark(r, 2)
        x += CELL
    y += CELL
DEC_DENS = 4.33e-15   # F/um2 stacked (MOS 3.72 pF/1600 um2 + MIM 2 fF/um2)
decap_f = len(decaps)*CELL*CELL*DEC_DENS

# ---------------------------------------------------------------------------------------------------------------
core_area = (CORE[2]-CORE[0])*(CORE[3]-CORE[1])
def clip(r):
    return (max(r[0], CORE[0]), max(r[1], CORE[1]), min(r[2], CORE[2]), min(r[3], CORE[3]))
def area(r):
    return max(0, r[2]-r[0])*max(0, r[3]-r[1])
pad_in = sum(area(clip(f['rect'])) for f in fixed if f['kind'] == 'pad')
rsv_in = sum(area(clip(f['rect'])) for f in fixed if f['kind'] == 'rsv')
dig_a = DW*DH
blk_a = sum(INV[n]['w']*INV[n]['h'] for n in INV)
plc_a = sum(INV[n]['w']*INV[n]['h'] for n in placed)
fail_a = sum(INV[n]['w']*INV[n]['h'] for n in failures)
avail = core_area-pad_in-rsv_in-dig_a
free_after = float((grid.occ == 0).sum())*G*G

# rule audit on the result
audit = []
for a, v, d, s in RULES:
    if a in all_rects and v in all_rects:
        g = gap(all_rects[a], all_rects[v]); audit.append(dict(aggressor=a, victim=v, min_um=d, gap_um=round(g, 1), ok=g >= d, basis=s))

# congestion estimate ---------------------------------------------------------------------------------------------
# Bus demand from the macro pin groups (v5 LEF; W7-GEAR +40, R8-ARCH +41 on the capture bus), routed as L shapes
# from the macro edge to the block centre. Supply: M2/M3 horizontal+vertical at 0.56 um pitch (2 layers per
# direction incl. M4 for long runs), derated to 30 % over analog blocks (local routing/shielding) and 70 % in free area.
dig = all_rects['digital']
def ctr(n):
    r = all_rects[n]; return ((r[0]+r[2])/2, (r[1]+r[3])/2)
cfg_split = {'rf': 0.30, 'lo': 0.15, 'wired': 0.30, 'conv': 0.10, 'pll': 0.05, 'core': 0.05, 'debug': 0.05}
BUSES = []
for g, fr in cfg_split.items():
    members = [n for n in placed if INV[n]['grp'] == g and not n.startswith(('leaf', 'steer'))]
    for n in members:
        BUSES.append((n, 568*fr/len(members), 'W'))
for n in placed:
    if n.startswith('atb_grp'):
        BUSES.append((n, 114/7, 'W'))
BUSES += [('wrx_cap', 42+40+41, 'S'), ('wiredtx', 43, 'S'), ('adc_i', 13, 'S'), ('adc_q', 13, 'S'), ('dac_i', 14, 'S'),
          ('dac_q', 13, 'S'), ('clk_obs16', 255*0.3, 'N')]
TILE = 250.0
nx, ny = int(math.ceil((CORE[2]-CORE[0])/TILE)), int(math.ceil((CORE[3]-CORE[1])/TILE))
dem_h = np.zeros((ny, nx)); dem_v = np.zeros((ny, nx))
def tix(x, y):
    return min(nx-1, max(0, int((x-CORE[0])/TILE))), min(ny-1, max(0, int((y-CORE[1])/TILE)))
for n, bits, edge in BUSES:
    if n not in all_rects:
        continue
    tx, ty = ctr(n)
    if edge == 'W':
        sx, sy = dig[0], min(max(ty, dig[1]), dig[3])
    elif edge == 'S':
        sx, sy = min(max(tx, dig[0]), dig[2]), dig[1]
    else:
        sx, sy = min(max(tx, dig[0]), dig[2]), dig[3]
    # vertical first from the macro edge, then horizontal
    i0, j0 = tix(sx, sy); i1, j1 = tix(tx, ty)
    for j in range(min(j0, j1), max(j0, j1)+1):
        dem_v[j, i0] += bits
    for i in range(min(i0, i1), max(i0, i1)+1):
        dem_h[j1, i] += bits
blocked = np.zeros((ny, nx))
for j in range(ny):
    for i in range(nx):
        t = (CORE[0]+i*TILE, CORE[1]+j*TILE, CORE[0]+(i+1)*TILE, CORE[1]+(j+1)*TILE)
        i0, j0, i1, j1 = grid.idx(t)
        sub = grid.occ[j0:j1, i0:i1]
        blocked[j, i] = (sub == 1).mean() if sub.size else 1
tracks = 2*TILE/0.56
cap = tracks*(0.3*blocked+0.7*(1-blocked))
over_h = dem_h/cap; over_v = dem_v/cap
cong = np.maximum(over_h, over_v)
# exclude tiles inside the digital macro (its own router)
for j in range(ny):
    for i in range(nx):
        cxx, cyy = CORE[0]+(i+.5)*TILE, CORE[1]+(j+.5)*TILE
        if dig[0] <= cxx <= dig[2] and dig[1] <= cyy <= dig[3]:
            cong[j, i] = 0
hot = int((cong > 0.8).sum()); peak = float(cong.max())
util_tiles = blocked

report = dict(
    date='2026-11-13', die_um=DIE[2:], core_um=CORE, core_mm2=round(core_area/1e6, 3),
    pad_intrusion_mm2=round(pad_in/1e6, 3), reserves_mm2=round(rsv_in/1e6, 3), digital_mm2=round(dig_a/1e6, 3),
    available_for_blocks_mm2=round(avail/1e6, 3), block_demand_mm2=round(blk_a/1e6, 3),
    raw_margin_mm2=round((avail-blk_a)/1e6, 3),
    placed=len(placed), failed=failures, failed_mm2=round(fail_a/1e6, 3),
    free_whitespace_after_place_mm2=round(free_after/1e6+len(decaps)*CELL*CELL/1e6, 3),
    decap_cells=len(decaps), decap_nF=round(decap_f*1e9, 3),
    congestion=dict(tile_um=TILE, peak_demand_over_supply=round(peak, 2), tiles_over_80pct=hot,
                    hot_tiles=[[round(CORE[0]+(i+.5)*TILE), round(CORE[1]+(j+.5)*TILE), round(float(cong[j, i]), 2)]
                               for j in range(ny) for i in range(nx) if cong[j, i] > 0.8]),
    rule_audit=audit,
)
group_area = {}
for n in INV:
    group_area[INV[n]['grp']] = group_area.get(INV[n]['grp'], 0)+INV[n]['w']*INV[n]['h']/1e6
report['group_mm2'] = {k: round(v, 3) for k, v in sorted(group_area.items(), key=lambda x: -x[1])}
json.dump(dict(fixed=fixed, placed=placed, failures=failures, decaps=decaps), open(f'{OUT}/run/floorplan-s{SCEN}.json', 'w'), indent=0)
json.dump(report, open(f'{OUT}/run/report-s{SCEN}.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in report.items() if k not in ('rule_audit',)}, indent=0)[:3000])
print('rule fails:', [a for a in audit if not a['ok']])

# render -----------------------------------------------------------------------------------------------------------
S = 0.25   # px/um
PANEL = 520
Wpx, Hpx = int(DIE[2]*S)+PANEL, int(DIE[3]*S)+70
im = Image.new('RGB', (Wpx, Hpx), 'white'); d = ImageDraw.Draw(im)
try:
    F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
    FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
    FT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
except Exception:
    F = FB = FT = ImageFont.load_default()
def P(x, y):
    return (x*S, (DIE[3]-y)*S)
def box(r, fill, outline, w=1):
    a, b = P(r[0], r[3]), P(r[2], r[1]); d.rectangle([a, b], fill=fill, outline=outline, width=w)
COL = dict(rf=('#f6d5d5', '#b03030'), conv=('#ead9f2', '#7a3a9a'), lo=('#fde6c8', '#c06000'), pll=('#fff1c4', '#a07800'),
           wired=('#d6efdc', '#2a7a40'), core=('#dde7f5', '#2a5aa0'), debug=('#d4eef0', '#207080'))
box(DIE, '#f4f4ee', '#555', 2)
box(CORE, '#ffffff', '#999', 1)
# congestion shading (tiles > 0.8)
for j in range(ny):
    for i in range(nx):
        if cong[j, i] > 0.8:
            t = (CORE[0]+i*TILE, CORE[1]+j*TILE, CORE[0]+(i+1)*TILE, CORE[1]+(j+1)*TILE)
            box(t, '#ffd9d9' if cong[j, i] < 1.2 else '#ff9e9e', None)
for r in decaps:
    box(r, '#c9dcf2', '#a8c0e0')
for f in fixed:
    r = f['rect']
    if f['kind'] == 'digital':
        box(r, '#e9f27a', '#2040a0', 3)
        c = P((r[0]+r[2])/2, (r[1]+r[3])/2)
        d.text((c[0]-170, c[1]-30), 'DIGITAL MACRO', fill='#2040a0', font=FT)
        d.text((c[0]-120, c[1]+5), '1716 x 1640 um (DT-4a)', fill='#2040a0', font=FB)
    elif f['kind'] == 'pad':
        box(r, '#cfcfcf', '#444', 1); t = P(r[0], r[3]); d.text((t[0]+2, t[1]+2), f['name'].replace('pad_', '').upper(), fill='#222', font=F)
    else:
        box(r, '#fbf3cf', '#b09a40', 1); t = P(r[0], r[3]); d.text((t[0]+2, t[1]+1), f['name'].replace('rsv_', ''), fill='#806a10', font=F)
for n, p in placed.items():
    fill, ol = COL[p['grp']]
    rsv = n.endswith('_rsv')
    box(p['rect'], '#ffffff' if rsv else fill, ol, 2 if rsv else 1)
    if not n.startswith('leaf'):
        t = P(p['rect'][0], p['rect'][3]); lab = n + (' [R90]' if p['rot'] else '')
        if (p['rect'][2]-p['rect'][0])*S > 30:
            d.text((t[0]+2, t[1]+1), lab, fill=ol, font=FB if p['w']*p['h'] > 1e5 else F)
# rule violations
for a in audit:
    if not a['ok']:
        c1, c2 = P(*ctr(a['aggressor'])), P(*ctr(a['victim']))
        d.line([c1, c2], fill='#e00000', width=2)
# side panel
X0 = DIE[2]*S+12; yy = 10
d.text((X0, yy), f'Area pass 4 scenario S{SCEN} (v6 base)', fill='black', font=FB); yy += 22
R = report
lines = [f"core {R['core_mm2']} mm2; pads in core {R['pad_intrusion_mm2']};",
         f"reserves {R['reserves_mm2']}; digital {R['digital_mm2']}",
         f"available for blocks {R['available_for_blocks_mm2']} mm2",
         f"block demand {R['block_demand_mm2']} mm2 (no halo)",
         f"RAW MARGIN {R['raw_margin_mm2']} mm2",
         f"placed {R['placed']}, NOT PLACED {len(failures)} ({R['failed_mm2']} mm2)",
         f"stacked decap {R['decap_nF']} nF in leftovers",
         f"congestion: peak {R['congestion']['peak_demand_over_supply']}x,",
         f"  {R['congestion']['tiles_over_80pct']} tiles > 0.8 (red shading)",
         f"rule fails: {sum(1 for a in audit if not a['ok'])} (red lines)", '']
for l in lines:
    d.text((X0, yy), l, fill='#900' if 'NOT' in l or 'MARGIN' in l else 'black', font=F); yy += 15
d.text((X0, yy), 'DO NOT FIT (same scale):', fill='#a00000', font=FB); yy += 20
xx = X0
for n in failures:
    w, h = INV[n]['w']*S, INV[n]['h']*S
    if w > h and w > PANEL-30:
        w, h = h, w
    if xx+w > Wpx-8:
        xx = X0; yy += hmax+18 if 'hmax' in dir() else 0
    d.rectangle([xx, yy, xx+w, yy+h], fill='#f8d0d0', outline='#a00000')
    d.text((xx+2, yy+2), f"{n}\n{INV[n]['w']:.0f}x{INV[n]['h']:.0f}", fill='#700', font=F)
    hmax = max(h, locals().get('hmax', 0))
    xx += w+8
yy = max(yy+(hmax if failures else 0)+30, 600)
d.text((X0, yy), 'Legend', fill='black', font=FB); yy += 18
for g, (fl, ol) in COL.items():
    d.rectangle([X0, yy, X0+18, yy+12], fill=fl, outline=ol); d.text((X0+24, yy-1), g, fill='black', font=F); yy += 16
d.rectangle([X0, yy, X0+18, yy+12], fill='white', outline='#2a7a40', width=2); d.text((X0+24, yy-1), 'reserve (not designed)', fill='black', font=F); yy += 16
d.rectangle([X0, yy, X0+18, yy+12], fill='#c9dcf2', outline='#a8c0e0'); d.text((X0+24, yy-1), 'stacked MOS+MIM decap', fill='black', font=F); yy += 16
d.rectangle([X0, yy, X0+18, yy+12], fill='#cfcfcf', outline='#444'); d.text((X0+24, yy-1), 'pad family (core intrusion)', fill='black', font=F); yy += 16
title = ('programmable_transceiver_platform - floorplan v6 (GF180MCU, 3.93 x 5.12 mm) - 2026-11-13 - '
         'outline-level, current GDS outlines, UNROUTED, NOT a GDS assembly')
d.text((8, DIE[3]*S+20), title, fill='black', font=FB)
im.save(f'{OUT}/run/chip-ap4-s{SCEN}.png')
print('png', im.size)
