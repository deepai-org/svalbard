"""Full-chip assembly inventory: every master, instance, pad site and island.

Single source for the chip-level floorplan, GDS assembly and netlist binding
(`verification/run_chip_assembly.py`). Paths are relative to the repository
root. Nothing here is an estimate: block bounds always come from the GDS
(`abstracts.json`), never from this table.
"""
import json
from pathlib import Path

_here = Path(__file__).resolve()
PROJECT = _here.parents[2] if len(_here.parents) > 3 else Path('/repo/projects/programmable_transceiver_platform')
ROOT = PROJECT.parents[1]
A = 'projects/programmable_transceiver_platform/analog/'
PADS = A+'pads/generated/'
ISLAND_SUPPORT = 'scratch/island-support-20261108-075605'
import os
# Floorplan version: v4 (default, 2026-11-10 risk-register driven) or v3 (reproduces scratch/chip-assembly-dev).
FLOORPLAN = os.environ.get('PT_FLOORPLAN', 'v4')
# P4 (interface-changes): compact core_bias 925.7 x 326.0 (was 393.2 tall) for v4.
CORE_BIAS_ROUTED = 'scratch/core-bias-routing-20261109-101927' if FLOORPLAN == 'v3' else 'scratch/core-bias-routing-20261110-compact'
DIGITAL_OUTLINE = 'scratch/digital-outline'

# Provider 1x1 template (librelane/slots/slot_1x1.yaml at the pinned provider commit).
DIE = (0.0, 0.0, 3932.0, 5122.0)
CORE = (442.0, 442.0, 3490.0, 4680.0)
RING_INNER = 376.0          # pad-cell inner edge measured from each die edge
SITE_PITCH = {'west': 211.0, 'east': 211.0, 'north': 180.0, 'south': 180.0}

# Base ring: retained provider ring + seal ring + ID/marker cells, from the
# packaging-qualified assembly (analog/pads/packaging_assembly.py output).
BASE_RING_GDS = PADS+'packaging-assembly.gds'
BASE_RING_TOP = 'custom_assembly_candidate'

# master -> (gds, top cell, netlist, subckt, island)
MASTERS = {
    # rf island
    'lna': (A+'rf_rx/generated/lna.gds', 'pt_lna', A+'rf_rx/generated/lna.ext.spice', 'pt_lna', 'rf'),
    'rxmix_i': (A+'rf_rx/generated/rxmix_i.gds', 'pt_rxmix_i', A+'rf_rx/generated/rxmix_i.ext.spice', 'pt_rxmix_i', 'rf'),
    'rxmix_q': (A+'rf_rx/generated/rxmix_q.gds', 'pt_rxmix_q', A+'rf_rx/generated/rxmix_q.ext.spice', 'pt_rxmix_q', 'rf'),
    'bbfilter_i': (A+'rf_rx/generated/bbfilter_i.gds', 'pt_bbfilter_i', A+'rf_rx/generated/bbfilter_i.ext.spice', 'pt_bbfilter_i', 'rf'),
    'bbfilter_q': (A+'rf_rx/generated/bbfilter_q.gds', 'pt_bbfilter_q', A+'rf_rx/generated/bbfilter_q.ext.spice', 'pt_bbfilter_q', 'rf'),
    'txmix_i': (A+'rf_tx/generated/txmix_i.gds', 'pt_txmix_i', A+'rf_tx/generated/txmix_i.ext.spice', 'pt_txmix_i', 'rf'),
    'txmix_q': (A+'rf_tx/generated/txmix_q.gds', 'pt_txmix_q', A+'rf_tx/generated/txmix_q.ext.spice', 'pt_txmix_q', 'rf'),
    'txsum': (A+'rf_tx/generated/txsum.gds', 'pt_txsum', A+'rf_tx/generated/txsum.ext.spice', 'pt_txsum', 'rf'),
    'rfdriver': (A+'rf_tx/generated/rfdriver.gds', 'pt_rfdriver', A+'rf_tx/generated/rfdriver.ext.spice', 'pt_rfdriver', 'rf'),
    # conv island
    'adc_i': (A+'converters/generated/adc_i.gds', 'pt_adc_i', A+'converters/generated/adc_i.ext.spice', 'pt_adc_i', 'conv'),
    'adc_q': (A+'converters/generated/adc_q.gds', 'pt_adc_q', A+'converters/generated/adc_q.ext.spice', 'pt_adc_q', 'conv'),
    'dac_i': (A+'converters/generated/dac_i.gds', 'pt_dac_i', A+'converters/generated/dac_i.ext.spice', 'pt_dac_i', 'conv'),
    'dac_q': (A+'converters/generated/dac_q.gds', 'pt_dac_q', A+'converters/generated/dac_q.ext.spice', 'pt_dac_q', 'conv'),
    'refbuf': (A+'converters/generated/refbuf.gds', 'pt_refbuf', A+'converters/generated/refbuf.ext.spice', 'pt_refbuf', 'conv'),
    # pll island (analog-architecture supply 'pll': rfpll, wirepll, clockmux, clocktree, quadrature, cdr, refinput)
    'pll_ring': (A+'timing/generated/pll_ring.gds', 'pt_pll_ring', A+'timing/generated/pll_ring.ext.spice', 'pt_pll_ring', 'pll'),
    'clockmux': (A+'timing/generated/clockmux.gds', 'pt_clockmux', A+'timing/generated/clockmux.ext.spice', 'pt_clockmux', 'pll'),
    'prescale': (A+'timing/generated/prescale.gds', 'pt_prescale', A+'timing/generated/prescale.ext.spice', 'pt_prescale', 'pll'),
    'wordclk': (A+'timing/generated/wordclk.gds', 'pt_wordclk', A+'timing/generated/wordclk.ext.spice', 'pt_wordclk', 'pll'),
    'polyphase': (A+'timing/generated/polyphase.gds', 'pt_polyphase', A+'timing/generated/polyphase.ext.spice', 'pt_polyphase', 'pll'),
    'lo_ext': (A+'timing/generated/lo_ext.gds', 'pt_lo_ext', A+'timing/generated/lo_ext.ext.spice', 'pt_lo_ext', 'pll'),
    'cdr': (A+'wired_rx/generated/cdr.gds', 'pt_cdr', A+'wired_rx/generated/cdr.ext.spice', 'pt_cdr', 'pll'),
    # wired island
    'ctle': (A+'wired_rx/generated/ctle.gds', 'pt_ctle', A+'wired_rx/generated/ctle.ext.spice', 'pt_ctle', 'wired'),
    'detect': (A+'wired_rx/generated/detect.gds', 'pt_detect', A+'wired_rx/generated/detect.ext.spice', 'pt_detect', 'wired'),
    'rxlevel': (A+'wired_rx/generated/rxlevel.gds', 'pt_rxlevel', A+'wired_rx/generated/rxlevel.ext.spice', 'pt_rxlevel', 'wired'),
    'rxselect': (A+'wired_rx/generated/rxselect.gds', 'pt_rxselect', A+'wired_rx/generated/rxselect.ext.spice', 'pt_rxselect', 'wired'),
    'slicer': (A+'wired_rx/generated/slicer.gds', 'pt_slicer', A+'wired_rx/generated/slicer.ext.spice', 'pt_slicer', 'wired'),
    'termination': (A+'wired_rx/generated/termination.gds', 'pt_termination', A+'wired_rx/generated/termination.ext.spice', 'pt_termination', 'wired'),
    'wmon_sel': (A+'wired_rx/generated/wmon_sel.gds', 'pt_wmon_sel', A+'wired_rx/generated/wmon_sel.ext.spice', 'pt_wmon_sel', 'wired'),
    'wrx_cap': (A+'wired_rx/generated/wrx_cap.gds', 'pt_wrx_cap', A+'wired_rx/generated/wrx_cap.ext.spice', 'pt_wrx_cap', 'wired'),
    'wiredtx': (A+'wired_tx/generated/wiredtx.gds', 'pt_wiredtx', A+'wired_tx/generated/wiredtx.ext.spice', 'pt_wiredtx', 'wired'),
    'hsbias': (A+'wired_tx/generated/hsbias.gds', 'pt_wtx_hsbias', A+'wired_tx/generated/hsbias.ext.spice', 'pt_wtx_hsbias', 'wired'),
    'wtx_fallback_control': (A+'bringup_control/generated/pt_wtx_fallback_control.gds', 'pt_wtx_fallback_control',
                             A+'bringup_control/generated/pt_wtx_fallback_control.ext.spice', 'pt_wtx_fallback_control', 'wired'),
    # debug island (island_support design.ISLANDS['debug'])
    'bb_tap': (A+'rf_rx/generated/bb_tap.gds', 'pt_bb_tap', A+'rf_rx/generated/bb_tap.ext.spice', 'pt_bb_tap', 'debug'),
    'clk_obs': (A+'timing/generated/clk_obs.gds', 'pt_clk_obs', A+'timing/generated/clk_obs.ext.spice', 'pt_clk_obs', 'debug'),
    # P3: 16-input CLK_OBS cell (sources 8-14 observable); v4 places it on CLK_OBS, wclk_obs stays pt_clk_obs.
    'clk_obs16': (A+'timing/generated/clk_obs16.gds', 'pt_clk_obs16', A+'timing/generated/clk_obs16.ext.spice', 'pt_clk_obs16', 'debug'),
    'diff_clk_rx': (A+'timing/generated/diff_clk_rx.gds', 'pt_diff_clk_rx', A+'timing/generated/diff_clk_rx.ext.spice', 'pt_diff_clk_rx', 'debug'),
    'ring_osc': (A+'timing/generated/ring_osc.gds', 'pt_ring_osc', A+'timing/generated/ring_osc.ext.spice', 'pt_ring_osc', 'debug'),
    'vco_replica': (A+'timing/generated/vco_replica.gds', 'pt_vco_replica', A+'timing/generated/vco_replica.ext.spice', 'pt_vco_replica', 'debug'),
    # core (never switched)
    'aosc': (A+'timing/generated/aosc.gds', 'pt_aosc', A+'timing/generated/aosc.ext.spice', 'pt_aosc', 'core'),
    'por': (A+'core_support/por/gds/gf180mcu_ocd_ip__por.gds.gz', 'gf180mcu_ocd_ip__por',
            A+'core_support/por/netlist/layout/gf180mcu_ocd_ip__por.spice', 'gf180mcu_ocd_ip__por', 'core'),
    'core_bias': (CORE_BIAS_ROUTED+'/pt_core_bias_routed.gds', 'pt_core_bias', None, 'pt_core_bias', 'core'),
    # island support
    **{f'isw_{n}': (f'{ISLAND_SUPPORT}/layout/isw_{n}.gds', f'isw_{n}', f'{ISLAND_SUPPORT}/pex/isw_{n}/isw_{n}.pex.spice',
                    f'isw_{n}_pex', n) for n in ('wired', 'rf', 'pll', 'conv', 'debug')},
    'iso_clamp': (f'{ISLAND_SUPPORT}/layout/iso_clamp.gds', 'iso_clamp', f'{ISLAND_SUPPORT}/pex/iso_clamp/iso_clamp.pex.spice', 'iso_clamp_pex', 'core'),
    'atb_leaf_s': (f'{ISLAND_SUPPORT}/layout/atb_leaf_s.gds', 'atb_leaf_s', f'{ISLAND_SUPPORT}/pexd/atb_leaf_s/atb_leaf_s.pex.spice', 'atb_leaf_s_flat', 'core'),
    'atb_leaf_f': (f'{ISLAND_SUPPORT}/layout/atb_leaf_f.gds', 'atb_leaf_f', f'{ISLAND_SUPPORT}/pexd/atb_leaf_f/atb_leaf_f.pex.spice', 'atb_leaf_f_flat', 'core'),
    'atb_grp': (f'{ISLAND_SUPPORT}/layout/atb_grp.gds', 'atb_grp', f'{ISLAND_SUPPORT}/pexd/atb_grp/atb_grp.pex.spice', 'atb_grp_flat', 'core'),
    # P5: MOS decap filler tile 40 x 40 um, 3.72 pF, Metal1/Via1/Metal2 only (M3-M5 free above).
    'decap_tile': (A+'decap/generated/pt_decap_tile.gds', 'pt_decap_tile', A+'decap/generated/pt_decap_tile_ext.spice', 'pt_decap_tile', 'core'),
    'atb_pad': (f'{ISLAND_SUPPORT}/layout/atb_pad.gds', 'atb_pad', f'{ISLAND_SUPPORT}/pexd/atb_pad/atb_pad.pex.spice', 'atb_pad_flat', 'core'),
}

# Pad families at custom sites (stress-safe families, analog/pads README).
PAD_FAMILIES = {
    'rf_pair': (PADS+'stress-safe-families/rf-pair/pad.gds', 'rf_protected_pad_pair',
                PADS+'stress-safe-families/rf-pair/reference.spice', 'pad_reference'),
    'single_leg': (PADS+'stress-safe-families/single-leg/pad.gds', 'rf_protected_pad_pair',
                   PADS+'stress-safe-families/single-leg/reference.spice', 'pad_reference'),
    'refpad': (PADS+'stress-safe-families/reference/combined.gds', 'tx_with_primary',
               PADS+'stress-safe-families/reference/physical.spice', 'tx_protected_pad'),
    'wirepad': (PADS+'stress-safe-families/wired-receive-usb/combined.gds', 'tx_with_primary',
                PADS+'stress-safe-families/wired-receive-usb/physical.spice', 'tx_protected_pad'),
    'txpad': (PADS+'stress-safe-families/wired-transmit/combined.gds', 'tx_with_primary',
              PADS+'stress-safe-families/wired-transmit/physical.spice', 'tx_protected_pad'),
}

# v4: compact pad-family candidates (pads owner I8 / P1-P7, scratch/pad-compact): refpad 913 deep with inner-edge
# M5 pins, rf_pair/single_leg inner-edge pins, wirepad/txpad L-shaped (notches usable, PAD_NOTCH_UM). GDS only: the
# electrical models stay the canonical ones (netlist binding only; sims use the pads owner's models).
PADC = 'scratch/pad-compact/'
if FLOORPLAN != 'v3':
    PAD_FAMILIES = {
        'rf_pair': (PADC+'rf-pair/pad.gds', 'rf_protected_pad_pair', *PAD_FAMILIES['rf_pair'][2:]),
        # Published compact families (area recovery round 2, 2026-11-10 05:26): canonical paths, renamed tops.
        'single_leg': (PADS+'stress-safe-families/single-leg/pad.gds', 'pad_single_leg', *PAD_FAMILIES['single_leg'][2:]),
        'wirepad': (PADS+'stress-safe-families/wired-receive-usb/combined.gds', 'pad_wirepad', *PAD_FAMILIES['wirepad'][2:]),
        'txpad': (PADS+'stress-safe-families/wired-transmit/combined.gds', 'pad_txpad', *PAD_FAMILIES['txpad'][2:]),
        # HELD by the pads owner pending the LO (P1) / RF match (P2) reruns: v4 depends on the compact refpad (913 deep,
        # inner-edge M5 PAD_P/N/VCM pins) for the short LO legs; rf_pair bbox is unchanged (inner-edge pins only).
        'refpad': (PADC+'reference_clock/pad/combined.gds', 'tx_with_primary', *PAD_FAMILIES['refpad'][2:]),
    }
# Free notches of the L-shaped compact wired families (cell coordinates, pads owner table): no geometry on any layer.
PAD_NOTCH_UM = {'wirepad': (192.5, 914.9, 524.0, 1512.72), 'txpad': (144.2, 914.9, 484.0, 1226.72)} if FLOORPLAN != 'v3' else {}

# Custom pad cells: origin site (first site of the pair), family, edge, signals.
# The packaging assembly fixes the transform convention: west m45 at (26, y_site),
# east r90 at (3906, y_site); local x runs along the edge, local y into the core.
CUSTOM_PADS = [
    # name, family, edge, origin site, sites covered, (P, N) chip ports, replaces packaging cell
    ('pad_rf_rx', 'rf_pair', 'west', 'inputs[11].pad', ['inputs[11].pad', 'inputs[10].pad'], ('RF_RX_P', 'RF_RX_N'), 'custom_rf_receive'),
    ('pad_bb_i', 'rf_pair', 'west', 'inputs[9].pad', ['inputs[9].pad', 'inputs[8].pad'], ('BB_I_P', 'BB_I_N'), None),
    ('pad_bb_q', 'rf_pair', 'west', 'inputs[7].pad', ['inputs[7].pad', 'inputs[6].pad'], ('BB_Q_P', 'BB_Q_N'), None),
    ('pad_rf_tx', 'rf_pair', 'west', 'inputs[5].pad', ['inputs[5].pad', 'inputs[4].pad'], ('RF_TX_P', 'RF_TX_N'), 'custom_rf_transmit'),
    ('pad_aux_clk', 'rf_pair', 'west', 'inputs[3].pad', ['inputs[3].pad', 'inputs[2].pad'], ('AUX_CLK_P', 'AUX_CLK_N'), None),
    ('pad_ref', 'refpad', 'west', 'inputs[1].pad', ['inputs[1].pad', 'inputs[0].pad'], ('REF_IN', 'REF_IN_N'), 'custom_reference_clock'),
    ('pad_wire_rx', 'wirepad', 'east', 'bidir[14].pad', ['bidir[14].pad', 'bidir[15].pad'], ('WIRE_RX_P', 'WIRE_RX_N'), 'custom_wired_receive_usb'),
    ('pad_wclk_in', 'rf_pair', 'east', 'bidir[16].pad', ['bidir[16].pad', 'bidir[17].pad'], ('WCLK_IN_P', 'WCLK_IN_N'), None),
    ('pad_wire_tx', 'txpad', 'east', 'bidir[20].pad', ['bidir[20].pad', 'bidir[21].pad'], ('WIRE_TX_P', 'WIRE_TX_N'), 'custom_wired_transmit'),
    ('pad_wtx_ext', 'rf_pair', 'east', 'bidir[22].pad', ['bidir[22].pad', 'bidir[23].pad'], ('WTX_EXT_P', 'WTX_EXT_N'), None),
    # WMON: shared-protection B cell (single-leg minus bleed and rail shunt, clipped to one
    # site pitch) on 40 um rail/return buses to the WTX_EXT macro. ESD_TEST keeps the
    # complete single-leg cell (tapeout-plan tier 3: the clamp variant under test).
    ('pad_wmon', 'single_leg_b', 'east', 'bidir[24].pad', ['bidir[24].pad'], ('WMON', None), None),
    ('pad_esd_test', 'single_leg', 'east', 'bidir[25].pad', ['bidir[25].pad'], ('ESD_TEST', None), None),
]
# The wired families are wider than two sites (wirepad 524 um, txpad 484 um against a
# 422 um site pair) and their protection network sits 700-1270 um deep. Unmirrored they
# overlap the 913 um-deep debug pair cells at bidir[16]/[22] (102 / 62 um). Mirroring
# them along the edge keeps both bond positions but swaps P/N: WIRE_RX_P bonds at
# bidir[15] and WIRE_TX_P at bidir[21]. This is a bond-map/board change (recorded in
# the assembly report); the extra width then lies over the adjacent supply sites,
# where ring cells are only 350 um deep.
MIRRORED_PADS = {'pad_wire_rx': ('bidir[15].pad', 'bidir[14].pad'), 'pad_wire_tx': ('bidir[21].pad', 'bidir[20].pad')}

# Q-path mixers are mirrored copies of the I-path cells so the LO feed from the polyphase
# is symmetric about the I/Q centre line (path-to-tapeout 2.4 "symmetric shielded LO").
MIRROR_X = set()   # superseded by ORIENT (floorplan v2)

# Floorplan v2: explicit placement of the RF chain and the I/Q pairs (lower-left of the
# placed rect, um) and orientation. KLayout codes: R0, MX = mirror about the horizontal
# axis (y -> -y, Trans.M0), MY = mirror about the vertical axis (Trans.M90), R180.
# RX I/Q axis y = 1830: Q cells below (MX), I cells above (R0). Gaps are 8 um (halo - grid).
IQ_AXIS_Y = 1798.0
# Floorplan v3 (2026-11-10, scratch/chip-assembly-dev/floorplan-rationale.md): v2 RX/LO column kept, whole RX/converter
# group and the macro lowered 40 um (north escape channel above the macro), N-S routing corridor east of the ADCs,
# PA moved into the west pocket under RF_TX, RF ring PLL fixed next to the LO column, wired RX front end at the WIRE_RX
# bond end (pad -> CTLE short), steering buffer above the CDR.
FIXED_PLACEMENT = {
    # RF RX/LO column at RF_RX (inputs[11/10], y 1363-1673): LNA, Q mixer (MX), LO hub on the I/Q axis, I mixer.
    'lna': (955.0, 1274.0, 'R0'),
    'rxmix_q': (955.0, 1396.0, 'MX'),      # LO/RF pins (cell bottom-left) face the axis
    'lo_ext': (955.0, 1695.0, 'R0'),       # LO hub on the axis
    'rxmix_i': (955.0, 1911.0, 'R0'),
    'polyphase': (955.0, 2210.0, 'R0'),
    'txmix_i': (955.0, 2420.0, 'R0'),      # TX mixer pair: LO pins meet on a local axis
    'txmix_q': (955.0, 2522.0, 'MX'),
    'txsum': (1100.0, 2624.0, 'R0'),
    # PA in the west pocket between BB_Q (inputs[7/6]) and RF_TX (inputs[5/4]), whose provider sites (dvdd/dvss
    # 2629-3051) are only 350 um deep: 20 um under the RF_TX pad family, >= 800 um from the ADCs, 1.4 mm from the LNA.
    'rfdriver': (460.0, 2795.0, 'R0'),
    # RF ring PLL (on-chip LO source) above bbfilter_i: 0.5 mm to the polyphase, >= 100 um from the macro.
    'pll_host': (1330.0, 2750.0, 'R90'),
    'bbfilter_q': (1259.0, 860.0, 'MX'),     # 40 um channel x 1219-1259: RF/LO split, DAC->TX baseband
    'bbfilter_i': (1259.0, 1803.0, 'R0'),
    'adc_q': (1768.0, 552.8, 'MX'),
    'adc_i': (1768.0, 1803.0, 'R0'),
    'refbuf': (1259.0, 550.0, 'R0'),
    'dac_q': (452.0, 575.0, 'MX'),
    'dac_i': (452.0, 868.0, 'R0'),
    # Wired TX: serializer/driver west of the WIRE_TX pad family (x 2676, y 2431-2912), word side 18 um under the macro.
    'wiredtx': (2330.0, 2045.0, 'R0'),
    'attached_tx_buffer': (2330.0, 1830.0, 'R90'),
    # Wired RX: CTLE and selector in the band between WIRE_RX (top 1224) and WCLK_IN (from 1363) next to the
    # WIRE_RX bond-end port (x 3468, y 1129); slicer with the CDR ring beside it (phases -> samplers), CDR above;
    # termination/rxlevel at the pad family's control end (x 2390).
    'ctle': (3265.0, 1241.0, 'R90'),
    'rxselect': (3115.0, 1241.0, 'R90'),
    'slicer': (2842.0, 1241.0, 'R0'),
    'pll_cdr': (2633.0, 1241.0, 'R0'),
    'cdr': (2620.0, 1628.0, 'R0'),
    'termination': (2330.0, 1248.0, 'R0'),
    'rxlevel': (2437.0, 1248.0, 'R0'),
    # Core bias: DC current distribution, rotated into the north-west column.
    'core_bias': (960.0, 3370.0, 'R90'),     # top 4296: clear of the REF refpad (x<=1039 from y 4320)
    # TX ring beside the serializer (phases length-matched, WT2), pad steering drivers under WIRE_TX.
    'pll_tx': (2680.0, 1980.0, 'R0'),
    **{f'attached_tx_steering_{k}': (2890.0+148.0*(k % 4), 2278.0 if k < 4 else 2133.0, 'R0') for k in range(6)},
    # WTX_EXT receiver between the WIRE_TX pad family and the macro, next to the WIRE_TX T-coil reserve.
    'rx_wtx_ext': (2690.0, 2927.0, 'R0'),
    # conv island switch in the pocket above the TX mixers (its strap bars need 35 um above and below).
    'isw_conv': (1000.0, 2720.0, 'R0'),
}
ORIENT = {k: v[2] for k, v in FIXED_PLACEMENT.items()}

# Shared debug protection (families-report.json shared_debug_protection.decision).
SHARED_PROTECTION = [('pad_bb_i', 'pad_bb_q'), ('pad_wtx_ext', 'pad_wmon')]
BUS_WIDTH_UM = 40.0

# Provider ring cells kept as-is; checked against the contract site map.
PROVIDER_SITES = {
    'clk_pad': 'D2H[0] (selected_host_output = bi_t substitution)',
    'rst_n_pad': 'RESET_N (in_c, PD tied high = weak pull-down)',
    'analog[0].pad': 'ATB0', 'analog[1].pad': 'ATB1',
    'bidir[37].pad': 'CLK_OBS', 'bidir[38].pad': 'DBG_OBS0', 'bidir[39].pad': 'DBG_OBS1',
    'bidir[18].pad': 'WCLK_OBS', 'bidir[19].pad': 'WDBG_OBS',
}

ISLANDS = ('wired', 'rf', 'pll', 'conv', 'debug')
ISLAND_BIT = {'wired': 0, 'rf': 1, 'pll': 2, 'conv': 4, 'debug': 5}   # pt_regmap island_en bit
# Decoupling (consolidation-pass-2.md R5): one shared 1 nF MIM pool on the always-on
# core VDD next to the island-switch row, split into banks that each hang off the pool
# bus through a narrow FIB-cuttable Metal5 strap; plus small local decap behind each
# island switch. The local size is a placeholder of one unit (~20 pF) until it is sized
# from the switch inrush limit.
DECAP_POOL_BANKS = 24
DECAP_POOL_F = 1e-9
DECAP_LOCAL_UNITS = {'wired': 1, 'rf': 1, 'pll': 1, 'conv': 1, 'debug': 1}
SWITCH_ROW_SEED = (2750.0, 2150.0)
# v3: pool banks next to the switching loads (macro edges, wired TX, PA) instead of one central row.
POOL_SEEDS = [(3200.0, 4250.0), (3350.0, 4050.0), (1150.0, 4550.0), (2600.0, 600.0), (3000.0, 600.0),
              (700.0, 4050.0), (3300.0, 600.0), (1100.0, 2850.0), (3250.0, 1750.0), (650.0, 1250.0)]
LOCAL_SEEDS = {'wired': (3000.0, 2250.0), 'rf': (1300.0, 2950.0), 'pll': (1250.0, 3250.0), 'conv': (1300.0, 750.0),
               'debug': (3150.0, 4200.0)}
FIB_STRAP_UM = (10.0, 20.0)     # width x length of each bank's cuttable strap
MIM_UNIT_UM = 100.0          # cap_mim_2p0fF 100 x 100 um (Magic gencell, DRC-clean)
MIM_PITCH_UM = 110.0
MIM_F_PER_UM2 = 1.99e-15     # PDK cap_mim_2f0_m4m5_noshield area term
MIM_F_PER_UM = 0.238e-15     # perimeter term


# Demand-driven mitigation space (MANDATE "Mitigation tricks are demand-driven"): halo in um reserved around these
# instances for guard rings / deep n-well edges. Reported by floorplan.mitigation_report(); applied as a hard rule
# only once scratch/reviews/risk-register.* marks the mitigation demanded (cite the register ID here).
MITIGATION_HALO_UM = {n: 20.0 for n in ('lna', 'lo_ext', 'polyphase', 'pll_host', 'pll_tx', 'pll_cdr', 'core_bias',
                                         'adc_i', 'adc_q', 'refbuf', 'rfdriver', 'digital')}
MITIGATION_DEMANDED = {}     # instance -> risk-register ID (empty: register not yet published)

# Aggressor masters keep >= AGGRESSOR_KEEPOUT_UM from victim blocks during automatic placement (MANDATE rule 3).
AGGRESSOR_MASTERS = {'ring_osc', 'vco_replica', 'clk_obs', 'pll_ring'}
VICTIM_INSTANCES = {'lna', 'rxmix_i', 'rxmix_q', 'core_bias', 'adc_i', 'adc_q', 'refbuf', 'lo_ext', 'polyphase'}
AGGRESSOR_KEEPOUT_UM = 60.0

# consolidation-pass-2.md R1: three pll_ring instances may become two (Ring C owner
# rule; digital side confirmed in scratch/reviews/interface-changes.md). Selected with
# PT_PLL_RINGS=2; the default keeps the three instances of the current netlists.
import os
PLL_RINGS = ('pll_tx', 'pll_cdr', 'pll_host') if os.environ.get('PT_PLL_RINGS', '3') == '3' else ('pll_tx', 'pll_cdr')


def instances(have_wrx_cap):
    """(instance, master, island, seed) in placement order (largest first within a seed)."""
    rows = [
        # Fixed RF chain (FIXED_PLACEMENT) is listed for the netlist; seeds unused.
        *[(n, n, 'rf', (0, 0)) for n in ('bbfilter_i', 'bbfilter_q', 'rxmix_i', 'rxmix_q', 'rfdriver', 'txmix_i',
                                         'txmix_q', 'txsum', 'lna')],
        # Clocking: RF PLL (pll_host) in the north-west column away from the LNA and >= 200 um
        # from the macro; wired rings next to their samplers (pll_cdr at the CDR, pll_tx at the
        # serializer); clock tree next to the macro.
        *[(n, 'pll_ring', 'pll', {'pll_tx': (2450, 2250), 'pll_cdr': (2700, 1450), 'pll_host': (1150, 3200)}[n])
          for n in PLL_RINGS],
        ('lo_ext', 'lo_ext', 'pll', (0, 0)), ('polyphase', 'polyphase', 'pll', (0, 0)),
        ('clockmux', 'clockmux', 'pll', (1100, 3900)), ('prescale', 'prescale', 'pll', (1100, 3950)),
        ('wordclk', 'wordclk', 'pll', (1200, 3150)), ('cdr', 'cdr', 'pll', (2650, 1350)),
        # Converters (fixed).
        ('adc_i', 'adc_i', 'conv', (0, 0)), ('adc_q', 'adc_q', 'conv', (0, 0)),
        ('dac_i', 'dac_i', 'conv', (0, 0)), ('dac_q', 'dac_q', 'conv', (0, 0)), ('refbuf', 'refbuf', 'conv', (0, 0)),
        # Wired RX at the WIRE_RX pad inner end (x 2390, y 703-1224): termination/CTLE, then
        # slicer/capture/CDR north of it, toward the macro's south-east corner.
        ('termination', 'termination', 'wired', (2300, 1300)), ('ctle', 'ctle', 'wired', (2420, 1320)),
        ('rxselect', 'rxselect', 'wired', (2530, 1320)), ('rxlevel', 'rxlevel', 'wired', (2300, 1450)),
        ('detect', 'detect', 'wired', (2850, 1500)), ('slicer', 'slicer', 'wired', (2500, 1500)),
        ('wmon_sel', 'wmon_sel', 'wired', (2300, 1600)),
        # Wired TX next to WIRE_TX (x 2676, y 2431-2912), under the macro's south-east corner.
        ('wiredtx', 'wiredtx', 'wired', (2500, 2550)), ('hsbias', 'hsbias', 'wired', (2700, 2200)),
        ('wtx_fallback_control', 'wtx_fallback_control', 'wired', (2700, 2250)),
        # Debug island cells next to the sites they serve.
        ('bb_tap_i', 'bb_tap', 'debug', (1000, 2750)), ('bb_tap_q', 'bb_tap', 'debug', (1150, 2750)),
        ('bb_tap_wmon', 'bb_tap', 'debug', (3100, 4100)),
        ('rx_aux_clk', 'diff_clk_rx', 'debug', (550, 3850)), ('rx_wclk_in', 'diff_clk_rx', 'debug', (2900, 1400)),
        ('rx_wtx_ext', 'diff_clk_rx', 'debug', (3200, 4100)),
        ('clk_obs', 'clk_obs', 'debug', (1200, 4400)), ('wclk_obs', 'clk_obs', 'debug', (2900, 1900)),
        ('ring_osc', 'ring_osc', 'debug', (1200, 4300)), ('vco_replica', 'vco_replica', 'debug', (1200, 4300)),
        # Core: bias at the wired/RF boundary, central to the islands; POR/AOSC at RESET_N.
        ('core_bias', 'core_bias', 'core', (2700, 1950)), ('por', 'por', 'core', (1200, 470)),
        ('aosc', 'aosc', 'core', (1200, 470)),
    ]
    if have_wrx_cap:
        rows.append(('wrx_cap', 'wrx_cap', 'wired', (2650, 1550)))
    # Island switches form one row next to the shared decap pool (R5).
    # Floorplan v2: each switch at its own island (short VISL feed), not one central row.
    isw_seed = {'wired': (3000, 2250), 'rf': (1300, 2950), 'pll': (1250, 3250), 'conv': (1100, 2900),
                'debug': (3150, 4200)}
    rows += [(f'isw_{n}', f'isw_{n}', n, isw_seed[n]) for n in ISLANDS]
    # Floorplan v4: per-instance master swaps and seeds for the automatically placed rows.
    return [(n, MASTER_SWAP.get(n, m), i, SEED_OVERRIDE.get(n, s)) for n, m, i, s in rows]


MASTER_SWAP = {}
SEED_OVERRIDE = {}


def atb_cells(controls):
    """ATB leaves/groups/pad switches with seeds near their group's nodes."""
    nodes = {n['code']: n for n in controls['atb_nodes'] if n.get('hardware', True)}
    group_seed = {'core_ref_trunks': (2700, 1950), 'characterization': (1180, 1200),
                  'core_ref_supply': (2700, 1950), 'rf': (1250, 3300), 'wired': (3000, 1300),
                  'pll_conv': (1150, 3700), 'characterization_debug': (1180, 1200)}
    rows = []
    for bus in (0, 1):
        for gi, g in enumerate(controls['atb_groups'][f'atb{bus}']):
            seed = group_seed.get(g['name'], (1700, 1900))
            rows.append((f'atb{bus}_grp{gi}', 'atb_grp', 'core', seed))
            for code in g['codes']:
                rows.append((f'atb{bus}_leaf{code}', 'atb_leaf_f' if bus == 0 else 'atb_leaf_s', 'core', seed))
        rows.append((f'atb{bus}_pad', 'atb_pad', 'core', (1100 if bus else 1250, 4600)))
    return rows


def mim_unit_f():
    return MIM_UNIT_UM**2*MIM_F_PER_UM2+4*MIM_UNIT_UM*MIM_F_PER_UM


def decap_banks():
    """(name, net island, units, seed): pool banks on core VDD, local decap per island."""
    import math
    need = math.ceil(DECAP_POOL_F/mim_unit_f()-1e-9)
    per = [need//DECAP_POOL_BANKS+(1 if k < need % DECAP_POOL_BANKS else 0) for k in range(DECAP_POOL_BANKS)]
    rows = [(f'decap_pool{k}', 'core', per[k], POOL_SEEDS[k % len(POOL_SEEDS)]) for k in range(DECAP_POOL_BANKS)]
    rows += [(f'decap_local_{n}', n, u, LOCAL_SEEDS[n]) for n, u in DECAP_LOCAL_UNITS.items()]
    return rows


def contract_sites():
    c = json.loads((PROJECT/'spec/contract.json').read_text())
    return c['assembly_policy']['provider_site_inventory']['ordered_sites_by_side'], c['assembly_policy']['candidate_signal_sites']


# Interface-architecture reservations (spec/interface-architecture-changes.md, S1-S10):
# pad-edge host DDR/gearbox regions (156.25 MHz), T-coil / low-C pad room at the wired
# pads. Sizes are placeholders until the owners publish layouts.
RESERVES = [
    ('rsv_d2h_gearbox', (470.0, 452.0, 2700.0, 499.0), 'south D2H DDR/gearbox under clk_pad, bidir[0..9] (v3: 48 um tall, '
     'placeholder until the S2 gearbox layout exists)'),
    ('rsv_h2d_gearbox', (2990.0, 4480.0, 3480.0, 4670.0), 'north H2D DDR/gearbox for bidir[26..27]'),
    ('rsv_corridor_s', (2243.0, 508.0, 2320.0, 3045.0), 'v3 N-S routing corridor: macro S edge -> south gearbox (D2H '
     'word/4 bus), DAC data along the south strip (y 510-545) to the DACs, adc_q data, SPI, wired RX data'),
    ('rsv_tcoil_wire_tx', (2900.0, 2922.0, 3470.0, 3042.0), 'T-coils at the north (bond) end of WIRE_TX'),
]


# =====================================================================================================================
# Floorplan v4 (2026-11-10, scratch/chip-assembly-v4/floorplan-v4-rationale.md): driven by the risk register
# (scratch/reviews/risk-register.*). Register IDs are cited per item. Selected with PT_FLOORPLAN=v4 (default).
# =====================================================================================================================
DIGITAL_ORIGIN = (1395.0, 3060.0)
DIGITAL_SIZE = None              # None: from the digital LEF (1580 x 1580)
if FLOORPLAN == 'v4':
    # ---- Macro (SUB-01 / RA-7: macro<->adc_i >= 300 um, floor 210 um floating, distance first). A 1580-tall macro on the
    # north edge leaves 2604 um below it for a 2490 um I/Q ADC stack: <= 114 um. v4 therefore REQUESTS a macro re-aspect
    # (interface I12, same 2.4964 mm2): 1716 x 1454.8, top-aligned, east edge at the WTX_EXT/WMON/ESD_TEST limit
    # (x 2993 - 15), west edge 10 um from the DAC column -> 238 um. PT_MACRO=square keeps 1580 x 1580 (113 um, the RA-7
    # DNW fallback). H2D/debug_cfg pins move to the E edge north end, which abuts the H2D gearbox (no N escape channel).
    MACRO_SHAPE = os.environ.get('PT_MACRO', 'wide')
    if MACRO_SHAPE == 'wide':
        DIGITAL_SIZE = (1716.0, round(2496400.0/1716.0, 3))
        DIGITAL_ORIGIN = (1262.0, round(4670.0-DIGITAL_SIZE[1], 3))
    else:
        DIGITAL_ORIGIN = (1398.0, 3090.0)
    _dac_x = 969.1 if MACRO_SHAPE == 'wide' else 1105.1
    # ---- West pad map (bond-map change, board B19/B3). LO-I (REF) and LO-Q (AUX) sit at P7/P5, both sides of the
    # dvdd/dvss pair, so the LO hub sits midway between their inner-edge pins: legs 502/503 um, equal by
    # construction (XT-01, A4). BB_I separates the RF_RX bonds from the LO bonds (XT-08); RF_TX takes P3 next to LO-Q
    # exactly as RF_TX/AUX were adjacent in v3 (BW-01 'maybe', unchanged); BB_Q moves to P1. AUX uses the refpad master
    # like REF: identical pad cells, dC = 0 by construction (IQ-03).
    CUSTOM_PADS = [
        ('pad_rf_rx', 'rf_pair', 'west', 'inputs[11].pad', ['inputs[11].pad', 'inputs[10].pad'], ('RF_RX_P', 'RF_RX_N'), 'custom_rf_receive'),
        ('pad_bb_i', 'rf_pair', 'west', 'inputs[9].pad', ['inputs[9].pad', 'inputs[8].pad'], ('BB_I_P', 'BB_I_N'), None),
        ('pad_ref', 'refpad', 'west', 'inputs[7].pad', ['inputs[7].pad', 'inputs[6].pad'], ('REF_IN', 'REF_IN_N'), 'custom_reference_clock'),
        ('pad_aux_clk', 'refpad', 'west', 'inputs[5].pad', ['inputs[5].pad', 'inputs[4].pad'], ('AUX_CLK_P', 'AUX_CLK_N'), None),
        # Package analysis (spec/package-channel.md): RF_TX away from AUX_CLK, next to a ground contact -> P1; BB_Q -> P3.
        ('pad_bb_q', 'rf_pair', 'west', 'inputs[3].pad', ['inputs[3].pad', 'inputs[2].pad'], ('BB_Q_P', 'BB_Q_N'), None),
        ('pad_rf_tx', 'rf_pair', 'west', 'inputs[1].pad', ['inputs[1].pad', 'inputs[0].pad'], ('RF_TX_P', 'RF_TX_N'), 'custom_rf_transmit'),
        *[p for p in CUSTOM_PADS if p[2] == 'east'],
    ]
    MASTER_SWAP = {'clk_obs': 'clk_obs16'}          # P3
    _ax = 1731.0                                     # RX I/Q axis (v3 1798; lowered with the thinner D2H strip)
    FIXED_PLACEMENT = {
        # RX: LNA on the I/Q axis between the mirrored mixers (equal LNA->mixer feeds, XT-02), right at the RF_RX
        # inner-edge pins (y 1651-1667). Filters/ADCs 18 um west of v3 (channel A 42 um) so the r-ac3 CDR fits.
        'lna': (955.0, _ax-55.6, 'R0'),
        'rxmix_q': (955.0, _ax-55.6-10.0-289.1, 'MX'),
        'rxmix_i': (955.0, _ax+55.6+10.0, 'R0'),
        'bbfilter_q': (1260.7, _ax-5.0-932.2, 'MX'),
        'bbfilter_i': (1260.7, _ax+5.0, 'R0'),
        'adc_q': (1769.7, _ax-5.0-1239.2, 'MX'),     # bottom 486.8: 10 um over the 24 um D2H strip
        'adc_i': (1769.7, _ax+5.0, 'R0'),            # top 2977.2 -> 238 um (wide) / 113 um (square) to the macro
        # Bias in the south-west corner: 2.4 mm from the macro (SUB-02/RA-8), 3 mm from the PA (SUB-07/TH-01). The
        # D2H lanes of clk_pad/bidir[0..2] run in the 10 um strip under it (y 442-452) to the gearbox east of x 1388.
        'core_bias': (452.0, 452.0, 'R0'),
        'refbuf': (857.0, 1047.0, 'R0'),             # VREF reservoir in the pocket under rxmix_q; shielded VREF (XT-04)
        # LO hub midway between the LO-I (P7, y 2231) and LO-Q (P5, y 3075) inner-edge pins: legs 502/503 um.
        'lo_ext': (1019.0, 2420.0, 'R0'),          # 233.7 x 465.4 (republished 06:09); centre y 2652.7
        # TX mixers and summer right above the hub (A4: mixers within 0.5 mm of lo_ext).
        'txmix_q': (1019.0, 2895.6, 'MX'),
        'txmix_i': (1019.0, 2996.8, 'R0'),
        'txsum': (1019.0, 3098.0, 'R0'),
        # Internal-LO source in pocket B: 426 um from bbfilter_i (SUB-05/RA-9 >= 200), 935 um from adc_i; active only
        # without the external LO, so its LOI crossing of the LO-I leg is mode-exclusive.
        'pll_host': (457.0, 2627.0, 'R90'),
        'polyphase': (457.0, 2836.1, 'R0'),
        # DACs beside the macro W edge (10 um; no DAC bus on the south strip, XT-04); a 30 um channel x 939-969 west of
        # them carries the txsum->PA line north.
        'dac_q': (_dac_x, 3160.0, 'M135'),
        'dac_i': (_dac_x+4.0, 3844.5, 'R90'),
        # PA at RF_TX (P3 inner-edge pins y 3761-3777): R180 puts its port corner at the pins.
        'rfdriver': (454.0, 4066.0, 'MY'),        # top of the NW pocket, port corner toward the P1 (RF_TX) pins
        # Debug taps: BB_I tap at the P9 pins; BB_Q tap next to the PA pocket on its way to P1.
        'bb_tap_i': (1019.0, 2100.0, 'R0'),
        # CLK_OBS cell (P3, 16 inputs) rotated into the north-west pocket; its pad (bidir[37], x 1208) is reached along
        # the 15 um gap east of the BB_Q family and the north core edge.
        'clk_obs': (454.0, 3798.0, 'R90'),
        # Attached-TX interlock under the macro's south-east corner (v3: north-east; that area now holds the debug
        # oscillators and the H2D lanes).
        'bb_tap_wmon': (3380.0, 4012.0, 'R0'),        # WMON tap above ESD_TEST, ~0.35 mm from the WMON pad
    }
    if MACRO_SHAPE != 'wide':     # square fallback: no room under the macro for the interlock or the band MIM
        del FIXED_PLACEMENT['attached_tx_interlock']
    FIXED_PLACEMENT = {**FIXED_PLACEMENT,
        # Always-on oscillator next to the macro, its consumer (fc_src[4]): > 2 mm from LNA/bbfilter/POR (SUB-04/RA-1).
        'aosc': (3270.0, 4400.0, 'R0'),
        # Wired TX (v3 positions; pads unchanged).
        'wiredtx': (2333.0, 2157.0, 'R0'),     # 97 um from adc_i (SUB-08 analysed distance)
        'attached_tx_buffer': (2330.0, 1942.0, 'R90'),
        'pll_tx': (2680.0, 2092.0, 'R0'),
        **{f'attached_tx_steering_{k}': (2890.0+148.0*(k % 4), 2278.0 if k < 4 else 2133.0, 'R0') for k in range(6)},
        'rx_wtx_ext': (2690.0, 2927.0, 'R0'),
        # Wired RX: CTLE/selector at the WIRE_RX bond end (v3); r-ac3 CDR (300 x 666) rotated into band A under the ring
        # and slicer (designed neighbours, phases -> samplers); termination/level detector in the wirepad notch.
        'ctle': (3265.0, 1241.0, 'R90'),
        'rxselect': (3115.0, 1241.0, 'R90'),
        'cdr': (2312.0, 1239.0, 'R0'),            # r-ac3, 301 x 693 (band A raised 112 um under the wide macro)
        'pll_cdr': (2624.0, 1239.0, 'R0'),
        'slicer': (2624.0, 1626.0, 'R0'),
        'rx_wclk_in': (3008.1, 1688.0, 'R0'),
        'wtx_fallback_control': (3209.0, 1688.0, 'R0'),
        'termination': (2408.0, 760.0, 'R0'),
        'rxlevel': (2515.0, 760.0, 'R0'),
    }
    ORIENT = {k: v[2] for k, v in FIXED_PLACEMENT.items()}
    _mb = DIGITAL_ORIGIN[1]
    RESERVES = [
        ('rsv_d2h_gearbox', (1387.7, 452.0, 2700.0, 476.0), 'south D2H DDR/gearbox, 24 um tall (digital I11: ~20k um2 '
         'needed, 31k reserved); clk_pad/bidir[0..2] lanes in the 10 um strip under core_bias; no DAC bus in v4'),
        ('rsv_h2d_gearbox', (2990.0, 4480.0, 3480.0, 4670.0), 'H2D DDR/gearbox, abuts the macro E edge north end'),
        ('rsv_corridor_s', (2255.2, 486.0, 2301.7, _mb-10.0), 'v4 N-S corridor (46.5 um): D2H word/4, adc_q data, '
         'wired RX data, SPI; 20 um from the ADC east edges (RA-6/XT-05); MOS decap tiles under it (Metal1-2)'),
        ('rsv_tcoil_wire_tx', (2900.0, 2922.0, 3470.0, 3042.0), 'T-coils at the north (bond) end of WIRE_TX'),
        ('rsv_lo_legs', (954.0, 2215.0, 1009.0, 3090.0), 'external LO legs (XT-01/A4): LO-I from the P7 pins north, '
         'LO-Q from the P5 pins south to the hub; G-S-G-S-G Metal4/5, fill excluded (MT-03)'),
        ('rsv_isolation_band', (1270.0, 2987.2, 2245.0, _mb-10.0), 'macro<->ADC isolation band (SUB-01): MIM pool only '
         '(no substrate taps), routing; no active blocks'),
    ]
    # Auto-placed MIM pool banks (3 units each) on the free core area; the near-macro MIM is explicit (MIM_FIXED_BANKS).
    DECAP_POOL_F = 0.36e-9
    POOL_SEEDS = [(3250.0, 4300.0), (3200.0, 600.0), (700.0, 2450.0), (600.0, 4400.0), (3000.0, 2050.0), (1500.0, 650.0)]
    DECAP_POOL_BANKS = 6
    # MIM only (no substrate taps) in the macro<->ADC isolation band: 8 x 1 units of 20.7 pF (PDN-02/RA-12, SUB-01).
    MIM_FIXED_BANKS = [('mim_isolation_band', 1290.0, 3020.0, 8, 1, 'rsv_isolation_band')] if MACRO_SHAPE == 'wide' else []
    LOCAL_SEEDS = {'wired': (3000.0, 2250.0), 'rf': (1150.0, 2350.0), 'pll': (700.0, 2500.0), 'conv': (2100.0, 520.0),
                   'debug': (3150.0, 4200.0)}
    DECAP_MOS_REGIONS = [
        ('mos_notch_wirepad', None, 'wirepad'),
        ('mos_notch_txpad', None, 'txpad'),
        ('mos_corridor', (2257.7, 492.0, 2299.7, _mb-12.0), None),
        ('mos_pocket_a', (452.0, 788.0, 1250.0, 1350.0), None),
        ('mos_sw_strip', (1388.0, 486.0, 1760.0, 785.0), None),
        # Under the macro's south-east corner, >= 240 um from adc_i (MOS taps carry macro ground; keep them out of the
        # isolation band).
        ('mos_macro_se', (2476.0, 3052.0, 2978.0, _mb-10.0), None),
    ]
    SEED_OVERRIDE = {
        'clockmux': (2850.0, 3120.0), 'prescale': (3150.0, 4250.0), 'wordclk': (2750.0, 3130.0),
        'wclk_obs': (3100.0, 4200.0), 'ring_osc': (3200.0, 4100.0),
        'vco_replica': (3300.0, 4250.0), 'rx_aux_clk': (1150.0, 3050.0), 'rx_wclk_in': (2900.0, 1400.0),
        'por': (700.0, 1250.0), 'detect': (2700.0, 600.0), 'isw_rf': (1150.0, 2400.0), 'isw_pll': (700.0, 2500.0),
        'isw_conv': (1550.0, 600.0), 'isw_debug': (3150.0, 4150.0), 'isw_wired': (2750.0, 900.0),
        'wmon_sel': (2650.0, 880.0), 'hsbias': (2950.0, 2080.0), 'bb_tap_wmon': (3400.0, 4100.0),
        'wrx_cap': (2900.0, 1500.0), 'bb_tap_q': (1100.0, 4600.0), 'attached_tx_interlock': (3300.0, 4200.0),
    }
    AGGRESSOR_MASTERS = {'ring_osc', 'vco_replica', 'clk_obs', 'clk_obs16', 'pll_ring', 'clockmux', 'prescale', 'wordclk'}
    VICTIM_INSTANCES = {'lna', 'rxmix_i', 'rxmix_q', 'core_bias', 'adc_i', 'adc_q', 'refbuf', 'lo_ext', 'polyphase',
                        'bbfilter_i', 'bbfilter_q', 'por'}
    # The SUB-01 north p+ ring (and DNW pockets in the square fallback) are inside adc_i (converters v4); the floorplan
    # demand is the macro-side gap (floorplan_rules REGISTER_DISTANCES), not a 20 um halo on every side.
    MITIGATION_DEMANDED = {}
    # Register-demanded distances (scratch/reviews/risk-register.*, RA rows): (aggressor, victim, min um, ID, basis).
    REGISTER_DISTANCES = [
        ('digital', 'adc_i', 300.0, 'SUB-01', 'RA-7: 300 um target, 210 um floor (FD floating); DNW pockets only below 210'),
        ('digital', 'adc_q', 300.0, 'SUB-01', 'as adc_i'),
        ('digital', 'core_bias', 100.0, 'SUB-02', 'RA-8 / I9: >= 100 um, bandgap at the far end'),
        ('digital', 'bbfilter_i', 100.0, 'SUB-01/SUB-05', 'baseband victim, v3 rule'),
        ('digital', 'lna', 1000.0, 'SUB-03', 'v3 rule'),
        ('pll_host', 'bbfilter_i', 200.0, 'SUB-05', 'RA-9: >= 200 um'),
        ('pll_host', 'adc_i', 200.0, 'SUB-05', 'RA-9: >= 200 um'),
        ('aosc', 'lna', 300.0, 'SUB-04', 'aosc EN not yet controllable (RA-1 open)'),
        ('aosc', 'bbfilter_q', 300.0, 'SUB-04', ''),
        ('aosc', 'bbfilter_i', 300.0, 'SUB-04', ''),
        ('aosc', 'por', 300.0, 'SUB-04', ''),
        ('aosc', 'adc_q', 300.0, 'SUB-04', ''),
        ('rfdriver', 'core_bias', 340.0, 'SUB-07/TH-01', 'analysed (not needed) at 340 um: keep at least that'),
        ('rfdriver', 'pll_host', 401.0, 'SUB-07', 'analysed at 401 um'),
        ('rfdriver', 'adc_i', 839.0, 'SUB-07', 'analysed at 839 um'),
        ('rfdriver', 'lna', 1000.0, 'SUB-07', 'v3 rule'),
        ('wiredtx', 'adc_i', 97.0, 'SUB-08/RA-10', 'v3 97 um analysed with the mode rule; keep at least that'),
    ]
