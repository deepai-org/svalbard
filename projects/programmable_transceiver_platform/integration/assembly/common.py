"""Shared inputs of the assembly flow (host python and the tool image alike; no tool imports here).

load(chip)        -> instances, ports, masters of integration/chips/<chip>/chip.conn (check_top.py parser), the macro's c_*
                     control outputs added to `digital` (chips/provider_io.macro_ctl: the conn does not list them)
gds_candidates(m) -> GDS files that hold master m, best first (published, then staged; scratch only where named)
Geometry constants of the 1x1 slot, the provider-site map and the no-route-over set live here as well.
"""
import hashlib, json, os, re, sys
A = os.path.dirname(os.path.abspath(__file__))
ROOT = '/repo' if A == '/asm' else os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(A))))
P = ROOT+'/projects/programmable_transceiver_platform'
sys.path.insert(0, P+'/integration/chips')
import check_top as ct
import provider_io as PIO
# KH_CONN=1 (off by default until both chips route clean): macro c_* ports, provider cells with their ties, the tied macro
# inputs hooked, provider cells bound in LVS, connectivity gate (KH-1..3, chips/provider_io.py, check_conn.py)
KH_CONN = os.environ.get('KH_CONN', '0') == '1'

DIE = (0.0, 0.0, 3932.0, 5122.0)
CORE = (452.0, 452.0, 3480.0, 4670.0)        # die-fit core; the provider cells end 376 um from the die edge
IO_INNER = 376.0                             # inner edge of the provider ring cells
RING_W, RING_GAP = 14.0, 4.0                 # power-delivery G8: core ring 2 x 25 um, may narrow to 2 x 12 (taken: 2 x 14)
PAD_CLEAR = float(os.environ.get('PAD_CLEAR', '40'))                             # pad footprint growth the packer keeps free (core ring detour 2 x 14 + 4 + spacing)
BASE_RING = 'projects/programmable_transceiver_platform/analog/pads/generated/packaging-assembly.gds'
MASK = 'scratch/integration/signoff-gap/dl/precheck-live/assets/golden_masks/mask_1x1.gds'
AN = 'projects/programmable_transceiver_platform/analog/'

# master -> [(gds relative to the repo root, top cell or None)], tried before the masters.txt netlist path
SPECIAL = {
    'por': [(AN+'core_support/por/gds/gf180mcu_ocd_ip__por.gds.gz', 'gf180mcu_ocd_ip__por')],
    'tx_steer': [(AN+'pads/generated/steering-buffer-compact/tx_steering_buffer_flat.gds', 'tx_steering_buffer_flat')],
    'term_buffer': [(AN+'pads/generated/termination-buffer-candidate/compact-array/buffer_compensated_flat.gds', 'buffer_compensated_flat')],
    'tx_interlock': [(AN+'pads/generated/packaging-assembly.gds', 'attached_tx_interlock')],
    'pt_core_bias_rf': [('scratch/core-bias-rf/routing/pt_core_bias_routed.gds', 'pt_core_bias_rf')],
    'pt_core_bias_wired': [('scratch/core-bias-wired/routing/pt_core_bias_routed.gds', 'pt_core_bias_wired')],
    'pt_lc_qvco5': [(AN+'timing/generated/lcvco/pt_lc_qvco5.gds', 'pt_lc_qvco5')],
    'pt_usb_txdrv': [(AN+'wired_tx/generated/usbdrv.gds', None)],
    'iso_clamp': [(AN+'island_support/generated/views/layout/iso_clamp.gds', 'iso_clamp')],
    'pad_tlp': [(AN+'pads/generated/tlp-site/pad_tlp_flat.gds', 'pad_tlp_flat')],
    'pad_rf_pair': [(AN+'pads/generated/stress-safe-families/rf-pair/pad.gds', None)],
    'pad_rftxpad': [(AN+'pads/generated/stress-safe-families/rf-tx/pad.gds', None)],
    'pad_single_leg': [(AN+'pads/generated/stress-safe-families/single-leg/pad.gds', None)],
    'pad_refpad': [(AN+'pads/generated/stress-safe-families/reference/combined.gds', None)],
    'pad_hspad': [(AN+'pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds', None)],
    'pad_wirepad': [(AN+'pads/generated/stress-safe-families/wired-receive-usb/combined.gds', None)],
    'pad_txpad': [(AN+'pads/generated/stress-safe-families/wired-transmit/combined.gds', None)],
}
# staged pad cells with the ASM-2 core-edge pins (pads owner, 2026-11-21), used before the published ones until they publish
STAGED_PADS = {}       # every custom pad family is published (option-A baselines; pinned pad_hspad ddcaaf79)
for _m, (_g, _c) in STAGED_PADS.items(): SPECIAL[_m] = [(_g, _c)]+SPECIAL[_m]
# owners' baseline handoffs (MANIFEST.json: {block: {gds, top}}), used before the published cells; the master is the top name
GRID_SNAP = {}       # master -> pitch: built with Metal5 channels on the grid phase; placed R0 with x0 = y0 = 0 (mod pitch)
HANDOFFS = ['scratch/timing/handoff']          # timing / wired RX (commit 860f6502)
for _d in HANDOFFS:
    try: _man = json.load(open(f'{ROOT}/{_d}/MANIFEST.json'))
    except OSError: continue
    for _k, _v in _man.items():
        if isinstance(_v, dict) and _v.get('gds') and _v.get('top') and os.path.exists(f'{ROOT}/{_d}/{_v["gds"]}'):
            SPECIAL[_v['top']] = [(f'{_d}/{_v["gds"]}', _v['top'])]+SPECIAL.get(_v['top'], [])
            if str(_v.get('grid', '')).startswith('m5_keep'): GRID_SNAP[_v['top']] = float(str(_v['grid']).split()[-1])
for _n in ('isw_wired', 'isw_rf', 'isw_pll', 'isw_conv', 'isw_debug', 'atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad'):
    _p = AN+f'island_support/generated/isw/{_n}.gds'            # isw / atb in isw/ first, then the tracked views (PDS-27)
    SPECIAL[_n] = ([(_p, _n)] if os.path.exists(ROOT+'/'+_p) else [])+[(AN+f'island_support/generated/views/layout/{_n}.gds', _n)]
# baseline (MANDATE 1, 2026-11-22): every instance real layout; owners' current best GDS before publication
SPECIAL.update({
    'iso_clamp_x4': [(AN+'island_support/generated/iso-family/iso_clamp_x4.gds', 'iso_clamp_x4')],
    'iso_pd': [(AN+'island_support/generated/iso-family/iso_pd.gds', 'iso_pd')],
    'pt_lna_ind': [(AN+'rf_rx/generated/lna_ind.gds', None)],
    'pt_lna_deg': [(AN+'rf_rx/generated/lna_deg.gds', None)],
    'pt_refvcm': [(AN+'core_support/distribution/generated/pt_refvcm.gds.gz', 'pt_refvcm')],
    'pt_txpad_bias': [(AN+'core_support/distribution/generated/pt_txpad_bias.gds.gz', 'pt_txpad_bias')],
})
# per-chip sources: (chip, master) -> [(gds, cell)]; the digital macro baseline of each chip (DG9-12)
# the owner's own LEF replaces the label-based abstract (the macro GDS carries labels of internal nets too)
CHIP_LEF = {(ch, 'pt_digital_macro'): f'scratch/digital-macro-baseline/{ch}/pt_digital_macro.lef' for ch in ('rf', 'wired')}
CHIP_SPECIAL = {(ch, 'pt_digital_macro'): [(f'scratch/digital-macro-baseline/{ch}/pt_digital_macro.gds', 'pt_digital_macro')] for ch in ('rf', 'wired')}
# staged blocks that replace a conn instance's master in the layout before the conn changes (coordinator, 2026-11-20):
# instance -> master, GDS, cell, placement rule (R0; x origin = x_mod[0] modulo x_mod[1] um), owner report with the grid ties
STAGED = {'wired': {'ptrim': dict(master='pt_ptrim', gds='scratch/timing/handoff/ptrim.gds', cell='pt_ptrim',
                                  x_mod=(313.05, 70.0), report='-', strap_w=10.5, via_pin='VSS'),   # r12 (wired RX), grid VSS Metal5 over its VSS strap
                    'wiredtx': dict(master='pt_wiredtx8', gds=AN+'wired_tx/generated/fast/pt_wiredtx8.gds', cell='pt_wiredtx8',
                                    x_mod=(20.75, 35.0), report='scratch/wired_tx/s13/top/out/report.json')}}
# ledger bookings that stand for a group of conn instances placed side by side on one bar (coordinator CB8-11: both
# wired_tx switch masters on one VISL bar beside pt_wiredtx8): booking -> members
# die-fit ledger bookings that no longer stand for anything (parts of pt_wiredtx8, power delivery 4.1c)
STALE_BOOK = {'wired': ['wtx_ser8d', 'wtx_mux8']}
GROUP_BOOK = {'rf': {'txmix_i': ['lo_txbuf', 'txmix_i']}}      # lo_txbuf abuts txmix_i (coordinator: hard rule)
# blocks the assembly places itself at fixed lower-left corners, R0 (power delivery 4.1c option B, commit c4276fd1):
# the wired_tx switch pair on the east edge beside the supply bonds, pt_wiredtx8 west of it, fed by a Metal5 bar
FIXED_PLACE = {'wired': {'isw_wired_tx_a': (2938.0, 2209.0), 'isw_wired_tx_b': (3206.0, 2209.0), 'wiredtx': (1913.95, 2209.0)}}
# island supply bars drawn by the assembly (Metal5, union of rectangles, die um), Via4 onto the listed instance pins under
# them; the grid gives way. pt_wired: RAIL_wired_tx from the isw_wired_tx_a/_b VISL bars to pt_wiredtx8's east edge
# (power delivery 4.1c option B, coordinator 2026-11-21: >= 180 um wide, IR closed at 56 mA); the run passes over the small
# blocks between them where they draw no Metal5, and enters the block's free corner (block x >= 598.7, y >= 236.1)
# rel = (instance, [(layer, block-coordinate rect)]) placed with that instance (R0); tie_vias = (instance, report tie names):
# Via4 where the Metal4 bar meets those Metal5 ties. pt_wiredtx8 WT57 (19367351): outline L 744.5 x 430.8, free corner
# x >= 598.7, y >= 266.36; island VDD ties T_main / T_post at y 423.1-430.8 (Metal5), east_island column; Metal4 band
# y 410.9-430.8, x 340-744 is island VDD only
ISLAND_BARS_OFF = False    # the VDD-VISL join (xy-overlap merge picked the VDD plate) is fixed: merge only Via4-joined Metal5
ISLAND_BARS = {'wired': [dict(net='RAIL_wired_tx', rects=[(2658.5, 2265.0, 3400.0, 2640.0)], expose=True,
                              rel=('wiredtx', [('Metal5', (598.9, 266.6, 744.5, 430.8)), ('Metal4', (340.0, 411.2, 744.5, 430.8))]),
                              tie_merge=('wiredtx', ['east_island']),
                              tie_vias=('wiredtx', ['T_main_2', 'T_main_3', 'T_post_0', 'T_post_1', 'T_post_2', 'T_post_3']),
                              vias=[('isw_wired_tx_a', 'VISL'), ('isw_wired_tx_b', 'VISL')]),
                          # wired_cap (PDS-19 72.9 mA design): bar over isw_wired_cap's outline, exposed, so the router never
                          # digs into the switch for VISL (RAIL_wired_cap joined VDD/VSS there, 2026-11-24); trunk to wrx_cap / ptrim later
                          dict(net='RAIL_wired_cap', rects=[], expose=True, rel=('isw_wired_cap', [('Metal5', 'pin:VISL')]),      # VISL strips only: over the whole switch it crowded PG / ISO / EN
                               vias=[('isw_wired_cap', 'VISL')])],
                # pt_rf rf_tx (PDS-20, 91.6 mA design): Metal5 bar over isw_rf_tx (joined to its VISL plate, Via4 onto VISL) and
                # 465 um south of it towards lo_txbuf / the TX mixers, cut round other blocks' Metal5 and the RF blocks; the bar
                # is a pin of RAIL_rf_tx (expose), so the router reaches the loads and isw_rf_tx_b from it, never VISL itself
                'rf': [dict(net='RAIL_rf_tx', rects=[], expose=True,
                            rel=('isw_rf_tx', [('Metal5', 'bbox'), ('Metal5', (0.0, -465.0, 243.1, 0.0))]),
                            vias=[('isw_rf_tx', 'VISL')])]}
# decap tiles the assembly places itself before the other blocks (power delivery 4.1d / PDS-16: the 14 tiles that did not
# place go inboard of pad_hs_rx, within 500 um of bidir[14], restoring 5.4 nF and the CDM reach): slot, count
FIXED_DECAP = {'wired': dict(slot=(2453.0, 960.0, 2953.0, 1440.0), count=14)}
# signal-flow adjacency the packer must keep (coordinator 2026-11-23, docs/layout/pt_<chip>-floorplan.png): pairs
# (a, b, max edge gap um, pull weight), applied both ways (whichever is placed second); relaxed only if impossible and
# then reported in floorplan.json 'relaxed'. KEEPAWAY adds (aggressor, victim, min gap um).
FLOW_ADJ = {
 'rf': [('lna_ind_p', 'lna', 8, 20), ('lna_ind_n', 'lna', 8, 20), ('lna_deg_p', 'lna', 8, 20), ('lna_deg_n', 'lna', 8, 20),
        ('rxmix_i', 'lo_ext', 120, 14), ('rxmix_q', 'lo_ext', 120, 14),
        ('dac_i', 'txmix_i', 200, 10), ('dac_q', 'txmix_q', 200, 10), ('dac_q', 'dac_i', 150, 6), ('txsum', 'txmix_i', 100, 4), ('rfdriver', 'txsum', 150, 4), ('rfdriver', 'pad_rf_tx', 150, 10), ('txmix_i', 'rfdriver', 150, 6), ('txmix_q', 'rfdriver', 150, 6),
        ('bbfilter_i', 'rxmix_i', 100, 5), ('bbfilter_q', 'rxmix_q', 100, 5), ('adc_i', 'bbfilter_i', 100, 5), ('adc_q', 'bbfilter_q', 100, 5),
        ('rx_ref_in', 'pad_ref', 100, 5), ('rxmix_i', 'lna', 100, 10), ('rxmix_q', 'lna', 150, 10),
        ('isw_rf_tx_b', 'isw_rf_tx', 8, 20), ('lo_txbuf', 'txmix_i', 60, 12), ('lo_txbuf', 'txmix_q', 60, 12), ('lo_txbuf', 'lo_ext', 1200, 16), ('rxmix_q', 'rxmix_i', 60, 14)],   # LO-ASM-6: LO branch <= ~2.1 mm   # PDS-20 switch pair; lo_txbuf r3 at the TX mixers
 'wired': [('ctle', 'pad_hs_rx', 60, 30), ('detect', 'pad_hs_rx', 150, 8), ('detect', 'ctle', 150, 6), ('slicer', 'ctle', 60, 12), ('ptrim', 'slicer', 60, 12), ('pll_cdr', 'ptrim', 80, 10),
           ('pll_tx', 'fix_wiredtx', 150, 8), ('ptrim', 'pll_cdr', 60, 8), ('slicer', 'ptrim', 60, 8), ('ctle', 'slicer', 100, 6), ('cdr', 'pll_cdr', 100, 4),
           ('wrx_cap', 'digital', 300, 2), ('wrx_cap', 'slicer', 200, 3),
           ('cascode_pump', 'pad_wire_tx', 60, 20)]}   # WT59: TX_CASCODE route <= 0.3 pF
# per-block halo (um) where many top-level nets meet: room for the router round the RF / LO chain (pt_rf at a 4 um default)
HALO_ITEMS = {'rf': {n: 15.0 for n in ('lo_ext', 'bbfilter_i', 'bbfilter_q', 'rxmix_i', 'rxmix_q', 'adc_i', 'adc_q', 'lna', 'lo_mmd', 'qvco', 'lo_txbuf', 'txmix_i', 'txmix_q', 'dac_i', 'dac_q', 'clockmux', 'core_bias')}}
FLOW_KEEPAWAY = {'rf': [('lo_txbuf', 'lna', 300), ('lo_txbuf', 'qvco', 200), ('rfdriver', 'pll_tx', 300), ('rfdriver', 'pll_cdr', 300), ('txmix_i', 'pll_cdr', 300), ('txmix_q', 'pll_cdr', 300)], 'wired': []}
# reserved slots for blocks not yet drawn, placed touching a partner (kept free of blocks; Metal1-3 blockage):
# name -> (w, h, partner). pt_lo_txbuf (LO owner, 2026-11-23): CML-to-CMOS I/Q buffer at the TX mixers; size provisional
# routing channels kept free of blocks (die um): pt_wired: wire_tx_data / controls from the macro's south edge straight down
# to pt_wiredtx8's top-edge pins (ASM-11a; block pins at die x ~1944-2034)
ROUTE_CHANNELS = {'wired': {'chan_wtxdata': (1924.0, 2650.0, 2134.0, 3027.0)}}
# grid kept 3 um off block signal pins (kl_place); pt_wired retried with wrx_cap r6 (Metal4 pins, TIM-33)
PIN_WINDOWS = {'rf': True, 'wired': True}
PIN_GATE_UM2 = 0.4      # gate area per analog block signal pin for the router antenna model: the SMALLEST gate seen in the deck (0.4-4.5 um2) is the pessimistic value (a 4.0 model left 2334 ANT.5)
# nets the deck still flags for antenna after the input diodes (2026-11-25, pt_rf tail 243): receiver pins modelled with a
# 0.02 um2 gate so the router jumps to Metal5 at the receiver
ANT_TIGHT = {'rf': ('HOST_CLK', 'BIAS_rfdriver', 'c_bbfilter_i_en', 'AUX_CK', 'ADCI_CODEB', 'CONV_CLK', 'CLK_OBS_DBG', 'c_lo_mmd_en', 'ATB1_LOCAL0', 'TXPH', 'ATBN_conv_ibias', 'ATB0', 'ADCI_OVL', 'ADCI_DONE', 'RING_OSC_CK', 'PLL_TX_FBCK')}
# grid slots no hook may take (die um, any slot containing the point): the second antenna pass (route.tcl) re-derives pin
# access after its jumpers and stops with DRT-1231 on a hook slot squeezed between two crossing signal nets
# (pt_rf VSS slot 978-998 x 4209.5-4217.5 under ATB1_LOCAL4 / CHAR_RP_DRV, 2026-11-25)
HOOK_SLOT_AVOID = {'rf': [(988.0, 4213.5)]}
# grid stitches (die um): extra strap metal (net, layer, rect) drawn after the strap cuts and clipped by the same avoid set;
# Via4 lands wherever it crosses its own net on the other layer. pt_rf: the Metal5 verticals over lo_lf (x 2837-3208,
# y 1058-1223) were cut off below qvco and fed no pin; two Metal4 bars in the lo_lf / qvco channel join them to the grid
# west of lo_lf (PDS-25 finding 3, 2026-11-25)
GRID_STITCH = {'rf': [('VDD', 'Metal4', (2690.0, 1213.6, 3275.0, 1217.6)), ('VSS', 'Metal4', (2690.0, 1219.0, 3275.0, 1223.0))]}
# nets that get top-level antenna diodes at their receivers (kl_place, pt_antdiode)
ANT_DIODE = {'rf': ('c_bbfilter_i_en', 'BIAS_rfdriver', 'ADCI_CODEB[0]', 'ADCI_CODEB[1]', 'ADCI_CODEB[2]', 'ADCI_CODEB[3]', 'ADCI_CODEB[4]', 'ADCI_CODEB[5]', 'ADCI_CODEB[6]', 'ADCI_CODEB[7]', 'ADCI_CODEB[8]', 'ADCI_CODEB[9]', 'ADCI_CODEB[10]', 'ADCI_CODEB[11]', 'ADCI_OVL', 'CLK_OBS_DBG', 'AUX_CK', 'HOST_CLK', 'CONV_CLK', 'PLL_TX_FBCK', 'c_lo_mmd_en')}
# masters whose supply pins are labelled only on Metal1 inside the cell: pins also on their own Metal4/5 of that net (kl_abstract)
PIN_UP = {'por': ('vdd3v3', 'vss')}
# conn blocks placed by the second pass, where decap tiles give way (2026-11-24: with the taller RF / ATB cells the packer
# left lna_deg_p, isw_rf_tx_b and char_rffet unplaced)
PASS2 = {'rf': ['lna_deg_p', 'isw_rf_tx_b', 'char_rffet']}
# blocks the packer must not rotate (none at present; pt_wrx_cap fixed south of the macro blocked the west routing, 2026-11-24)
NOROT = {}
# conn blocks the second pass must put touching a named partner (hard: decap gives way, else reported)
HARD_NEXT_TO = {'rf': {'lna_deg_p': ('lna', 8.0), 'isw_rf_tx_b': ('isw_rf_tx', 5000.0), 'char_rffet': ('digital', 5000.0)}}     # coordinator ASM-15 ruling: lna_deg_p within 8 um of the LNA; isw_rf_tx_b touching the rf_tx bar (it reaches 465 um south of isw_rf_tx)
BOOK_NEAR = {}     # pt_lo_txbuf is published (LO-ASM-4) and placed as a conn block next to the TX mixers
TWIN = {'pt_adc_q': 'pt_adc_i', 'pt_dac_q': 'pt_dac_i'}
# provider-ring instances of the conn (not core blocks): their pins are on the template's IO cells
PROVIDER = PIO.PROVIDER

# no top-level routing over these masters on any layer (RF, LO, rings, spirals: fill keep-out set `rf`,
# integration/signoff/fill/keepouts.json); other blocks may be crossed on Metal4 / Metal5 where they draw no metal
NO_OVER = {'pt_lc_qvco5', 'pt_lna_ind', 'pt_lna_deg', 'pt_lna', 'pt_rxmix_i', 'pt_rxmix_q', 'pt_txmix_i', 'pt_txmix_q',
           'pt_txsum', 'pt_rfdriver', 'pt_lo_ext', 'pt_lo_mmd', 'pt_lo_mmd_qdum', 'pt_pll_ring', 'pt_pll_ring_core',
           'pt_ring_osc', 'pt_vco_replica', 'wtx_tcoil_rsv'}

# GF180 5LM: (name, drawing, label, via below)
METALS = [('Metal1', (34, 0), (34, 10), None), ('Metal2', (36, 0), (36, 10), (35, 0)), ('Metal3', (42, 0), (42, 10), (38, 0)),
          ('Metal4', (46, 0), (46, 10), (40, 0)), ('Metal5', (81, 0), (81, 10), (41, 0))]


def load(chip):
    inst, ports, _w, err = ct.parse(ct.read_conn(f'{P}/integration/chips/{chip}/chip.conn'))
    assert not err, err
    if KH_CONN: PIO.macro_ctl(inst)
    masters = ct.load_masters(open(P+'/integration/chips/masters.txt').read())
    return inst, ports, masters


def master_pins(masters, m):
    md = masters.get(m)
    if not md: return []
    return (md['pins'] if md['kind'] != 'file' else ct.subckt_pins(md['path'], md['sub'])) or []


def gds_candidates(masters, m, chip=None):
    staged = json.load(open(ROOT+'/scratch/reviews/die-fit/m45free_staged.json'))
    out = [dict(gds=g, cell=c, kind='published' if g.startswith(AN) else 'scratch') for g, c in CHIP_SPECIAL.get((chip, m), [])+SPECIAL.get(m, [])]
    md = masters.get(m)
    if md and md.get('path') and m not in SPECIAL:
        stem = re.sub(r'(\.ext|\.pex|\.lvs|_ext)?\.spice$', '', os.path.relpath(md['path'], ROOT))
        out.append(dict(gds=stem+'.gds', cell=md['sub'], kind='published' if md['kind'] == 'file' else 'staged'))
    if m in staged and 'file' in staged[m]:
        out.append(dict(gds=staged[m]['file'].lstrip('/'), cell=staged[m].get('top'), kind='staged'))
    t = TWIN.get(m)
    if t and t in staged and 'file' in staged[t]:
        out.append(dict(gds=staged[t]['file'].lstrip('/'), cell=staged[t].get('top'), kind='staged-twin'))
    out = [c for c in out if os.path.exists(ROOT+'/'+c['gds'])]
    for c in out:
        c['sha256'] = hashlib.sha256(open(ROOT+'/'+c['gds'], 'rb').read()).hexdigest()[:16]
    return out


def bond(chip):
    return [l.split()[:4] for l in open(f'{P}/integration/chips/{chip}/bond_map.txt') if l.strip() and not l.startswith('#')]


def sites():
    return json.load(open(P+'/analog/pads/generated/provider-sites.json'))['sites']


# provider-ring pins of the conn: (instance, conn pin) -> (bond net of the site, IO cell pin). Output enables, drive and
# slew of the D2H cells go to every D2H site (one net, many cells).
def provider_pins(inst, bondrows):
    site_of = {}
    for site, side, net, i in bondrows: site_of.setdefault(net, []).append(site)
    out = []
    def add(i, pin, net, iopin):
        if i in inst and pin in inst[i]['pins'] and inst[i]['pins'][pin][1] != '-':
            for s in site_of.get(net, []): out.append((i, pin, s, iopin))
    add('host', 'rst_n', 'RESET_N', 'Y'); add('host', 'sclk', 'SPI_SCLK', 'Y'); add('host', 'cs_n', 'SPI_CS_N', 'Y')
    add('host', 'mosi', 'SPI_MOSI', 'Y'); add('host', 'miso', 'SPI_MISO', 'A'); add('host', 'miso_oe', 'SPI_MISO', 'OE')
    add('host', 'h2d_clk', 'H2D_CLK', 'Y')
    for k in range(10):
        add('host', f'h2d_pin[{k}]', f'H2D[{k}]', 'Y'); add('host', f'd2h_pin[{k}]', f'D2H[{k}]', 'A')
    add('host', 'd2h_clk_pin', 'D2H_CLK', 'A')
    for net in [f'D2H[{k}]' for k in range(10)]+['D2H_CLK']:
        add('host', 'd2h_oe', net, 'OE'); add('host', 'd2h_sl', net, 'SL')
        add('host', 'd2h_pdrv[0]', net, 'PDRV0'); add('host', 'd2h_pdrv[1]', net, 'PDRV1')
    for p, n in (('clk_obs', 'CLK_OBS'), ('dbg_obs0', 'DBG_OBS0'), ('dbg_obs1', 'DBG_OBS1')):
        add('debug_pads', p, n, 'A'); add('debug_pads', p+'_oe', n, 'OE')
    add('pad_por_bypass', 'Y', 'POR_BYPASS', 'Y')
    for i, n in (('atb0_io', 'ATB0'), ('atb1_io', 'ATB1')):
        add(i, 'ASIG5V', n, 'ASIG5V')
    return out


# provider-ring cells (KH_CONN): one record per provider bond site, every core pin bound to a net or tied to VDD / VSS
# (chips/provider_io.sites, transcribed from integration/pt_provider_io.sv)
def provider_sites(inst, bondrows):
    return PIO.sites(inst, bondrows)
