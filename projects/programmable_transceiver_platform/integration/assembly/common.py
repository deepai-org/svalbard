"""Shared inputs of the assembly flow (host python and the tool image alike; no tool imports here).

load(chip)        -> instances, ports, masters of integration/chips/<chip>/chip.conn (check_top.py parser)
gds_candidates(m) -> GDS files that hold master m, best first (published, then staged; scratch only where named)
Geometry constants of the 1x1 slot, the provider-site map and the no-route-over set live here as well.
"""
import hashlib, json, os, re, sys
A = os.path.dirname(os.path.abspath(__file__))
ROOT = '/repo' if A == '/asm' else os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(A))))
P = ROOT+'/projects/programmable_transceiver_platform'
sys.path.insert(0, P+'/integration/chips')
import check_top as ct

DIE = (0.0, 0.0, 3932.0, 5122.0)
CORE = (452.0, 452.0, 3480.0, 4670.0)        # die-fit core; the provider cells end 376 um from the die edge
IO_INNER = 376.0                             # inner edge of the provider ring cells
RING_W, RING_GAP = 14.0, 4.0                 # power-delivery G8: core ring 2 x 25 um, may narrow to 2 x 12 (taken: 2 x 14)
PAD_CLEAR = 40.0                             # pad footprint growth the packer keeps free (core ring detour 2 x 14 + 4 + spacing)
BASE_RING = 'projects/programmable_transceiver_platform/analog/pads/generated/packaging-assembly.gds'
MASK = 'scratch/integration/signoff-gap/dl/precheck-live/assets/golden_masks/mask_1x1.gds'
AN = 'projects/programmable_transceiver_platform/analog/'
IS = 'scratch/island-support-20261108-075605/'

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
    'iso_clamp': [(IS+'layout/iso_clamp.gds', 'iso_clamp')],
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
STAGED_PADS = {'pad_txpad': ('scratch/pads-core/esdopt/tx/sec/b/a12/pad_txpad.gds', 'pad_txpad'),
               'pad_wirepad': ('scratch/pads-core/esdopt/usb/build/b7/pad/combined.gds', 'tx_with_primary'),
               # pin-move-only variants of the published cells (core pins on the top edge, Metal4)
               'pad_rf_pair': ('scratch/pads-core/esdopt/pins/b/pad_rf_pair.gds', 'pad_rf_pair'),
               'pad_rftxpad': ('scratch/pads-core/esdopt/pins/b/pad_rftxpad.gds', 'pad_rftxpad'),
               'pad_single_leg': ('scratch/pads-core/esdopt/pins/b/pad_single_leg.gds', 'pad_single_leg'),
               'pad_hspad': ('scratch/pads-core/esdopt/pins/b/pad_hspad.gds', 'pad_hspad')}
for _m, (_g, _c) in STAGED_PADS.items(): SPECIAL[_m] = [(_g, _c)]+SPECIAL[_m]
for _n in ('isw_wired', 'isw_rf', 'isw_pll', 'isw_conv', 'isw_debug', 'atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad'):
    SPECIAL[_n] = [(IS+f'layout/{_n}.gds', _n)]
# staged blocks that replace a conn instance's master in the layout before the conn changes (coordinator, 2026-11-20):
# instance -> master, GDS, cell, placement rule (R0; x origin = x_mod[0] modulo x_mod[1] um), owner report with the grid ties
STAGED = {'wired': {'wiredtx': dict(master='pt_wiredtx8', gds=AN+'wired_tx/generated/fast/pt_wiredtx8.gds', cell='pt_wiredtx8',
                                    x_mod=(20.75, 35.0), report='scratch/wired_tx/s13/top/out/report.json')}}
# ledger bookings that stand for a group of conn instances placed side by side on one bar (coordinator CB8-11: both
# wired_tx switch masters on one VISL bar beside pt_wiredtx8): booking -> members
# die-fit ledger bookings that no longer stand for anything (parts of pt_wiredtx8, power delivery 4.1c)
STALE_BOOK = {'wired': ['wtx_ser8d', 'wtx_mux8']}
GROUP_BOOK = {}
# blocks the assembly places itself at fixed lower-left corners, R0 (power delivery 4.1c option B, commit c4276fd1):
# the wired_tx switch pair on the east edge beside the supply bonds, pt_wiredtx8 west of it, fed by a Metal5 bar
FIXED_PLACE = {'wired': {'isw_wired_tx_a': (2938.0, 2209.0), 'isw_wired_tx_b': (3206.0, 2209.0), 'wiredtx': (1913.95, 2209.0)}}
# island supply bars drawn by the assembly (Metal5, union of rectangles, die um), Via4 onto the listed instance pins under
# them; the grid gives way. pt_wired: RAIL_wired_tx from the isw_wired_tx_a/_b VISL bars to pt_wiredtx8's east edge
# (power delivery 4.1c option B, coordinator 2026-11-21: >= 180 um wide, IR closed at 56 mA); the run passes over the small
# blocks between them where they draw no Metal5, and enters the block's free corner (block x >= 598.7, y >= 236.1)
ISLAND_BARS = {'wired': [dict(net='RAIL_wired_tx', rects=[(2658.5, 2265.0, 3400.0, 2611.0), (2512.95, 2445.6, 2658.5, 2610.2)],
                              vias=[('isw_wired_tx_a', 'VISL'), ('isw_wired_tx_b', 'VISL')])]}
TWIN = {'pt_adc_q': 'pt_adc_i', 'pt_dac_q': 'pt_dac_i'}
# provider-ring instances of the conn (not core blocks): their pins are on the template's IO cells
PROVIDER = ('pt_host_physical', 'pt_debug_physical', 'atb_provider_pad', 'pad_strap', 'prov_supply', 'prov_supply_sig')

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
    masters = ct.load_masters(open(P+'/integration/chips/masters.txt').read())
    return inst, ports, masters


def master_pins(masters, m):
    md = masters.get(m)
    if not md: return []
    return (md['pins'] if md['kind'] != 'file' else ct.subckt_pins(md['path'], md['sub'])) or []


def gds_candidates(masters, m):
    staged = json.load(open(ROOT+'/scratch/reviews/die-fit/m45free_staged.json'))
    out = [dict(gds=g, cell=c, kind='published' if g.startswith(AN) else 'scratch') for g, c in SPECIAL.get(m, [])]
    md = masters.get(m)
    if md and md.get('path') and m not in SPECIAL:
        stem = re.sub(r'(\.ext|\.pex|_ext)?\.spice$', '', os.path.relpath(md['path'], ROOT))
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
