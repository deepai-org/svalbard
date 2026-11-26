"""Planning inputs of one chip (CHIP=rf|wired): placed run (KH_CONN=1, stages abstract floorplan place), its extract,
the hand placement and channels (<chip>_place.json), keep-away and adjacency rules with their sources."""
import json, os
A = os.path.dirname(os.path.abspath(__file__))
CHIP = os.environ.get('CHIP', 'rf')
ROOT = os.path.abspath(A + '/../../../../..')
RUN = os.environ.get('PLAN_RUN', f'{ROOT}/scratch/integration/fpplan-{CHIP}')
JSON = os.environ.get('PLAN_JSON', f'{RUN}/plan_extract.json')          # extract.py output
PLACE = json.load(open(os.environ.get('PLACE', f'{A}/{CHIP}_place.json')))
MACRO = 'digital'
FIXED = {k: tuple(v) for k, v in PLACE['hand'].items()}
CHANNELS = {k: tuple(v) for k, v in PLACE['channels'].items()}
MPITCH = 2.24
# channels decap tiles may occupy (they block Metal1-2 only; with the swapped grid Metal3 / Metal4 / Metal5 pass over them):
# not the macro escape rows (Metal2 pins) or pin-dense gaps
DECAP_CHANNELS = PLACE.get('decap_channels', [])
if CHIP == 'rf':
    KEEPOUTS = [r for v in json.load(open(RUN + '/fp_pads.json')).values() for r in v]          # pad footprints + 34 um (floorplan.py PAD_CLEAR rf)
    MFORBID = {'E': [(3290.0, 3600.0)]}       # macro east edge facing pad_aux_clk: no pins
    # keep-aways: die-fit fit.py RULES (v6, pt_rf), common.FLOW_KEEPAWAY, risk register LO-03 (rfdriver >= 1 mm from both rings)
    RULES = [('digital', 'adc_i', 210), ('digital', 'adc_q', 210), ('digital', 'core_bias', 100), ('digital', 'bbfilter_i', 100), ('digital', 'bbfilter_q', 100),
             ('digital', 'lna', 1000), ('digital', 'qvco', 300), ('pll_cdr', 'qvco', 500), ('pll_tx', 'qvco', 500), ('pll_cdr', 'adc_i', 200), ('pll_cdr', 'bbfilter_i', 200),
             ('aosc', 'lna', 300), ('aosc', 'por', 300), ('aosc', 'adc_q', 300), ('rfdriver', 'core_bias', 340), ('rfdriver', 'adc_i', 839), ('rfdriver', 'lna', 1000),
             ('qvco', 'lna', 250), ('west_edge', 'qvco', 1500), ('rf_tx_band', 'qvco', 800),
             ('lo_txbuf', 'lna', 300), ('lo_txbuf', 'qvco', 200), ('rfdriver', 'pll_tx', 1000), ('rfdriver', 'pll_cdr', 1000), ('txmix_i', 'pll_cdr', 300), ('txmix_q', 'pll_cdr', 300)]
    VIRTUAL = {'west_edge': (0.0, -1e6, 0.0, 1e6), 'rf_tx_band': (-1e6, 4281.0, 1e6, 4663.0)}
    G4 = {'isw_rf_rx': ('W', 2666.5), 'isw_rf_tx': ('W', 3510.5), 'isw_lod': ('E', 2033.5), 'isw_lo': ('E', 2033.5), 'isw_conv': ('W', 978.5),
          'isw_pll': ('E', 4143.5), 'isw_debug': ('E', 556.5)}
    # common.FLOW_ADJ (pt_rf) + die-fit targets (pads, LO synthesiser partners)
    ADJ = [(a, b, d, 1) for a, b, d in [
        ('lna_ind_p', 'lna', 8), ('lna_ind_n', 'lna', 8), ('lna_deg_p', 'lna', 8), ('lna_deg_n', 'lna', 8), ('rxmix_i', 'lo_ext', 120), ('rxmix_q', 'lo_ext', 120),
        ('dac_i', 'txmix_i', 200), ('dac_q', 'txmix_q', 200), ('dac_q', 'dac_i', 150), ('txsum', 'txmix_i', 100), ('rfdriver', 'txsum', 150), ('rfdriver', 'pad_rf_tx', 150),
        ('txmix_i', 'rfdriver', 150), ('txmix_q', 'rfdriver', 150), ('bbfilter_i', 'rxmix_i', 100), ('bbfilter_q', 'rxmix_q', 100), ('adc_i', 'bbfilter_i', 100),
        ('adc_q', 'bbfilter_q', 100), ('rx_ref_in', 'pad_ref', 100), ('rxmix_i', 'lna', 100), ('rxmix_q', 'lna', 150), ('isw_rf_tx_b', 'isw_rf_tx', 8),
        ('lo_txbuf', 'txmix_i', 60), ('lo_txbuf', 'txmix_q', 60), ('lo_txbuf', 'lo_ext', 1200), ('rxmix_q', 'rxmix_i', 60),
        ('lna', 'pad_rf_rx', 40), ('bb_tap_i', 'pad_bb_i', 100), ('bb_tap_q', 'pad_bb_q', 100), ('rx_aux_clk', 'pad_aux_clk', 100),
        ('lo_mmd', 'qvco', 100), ('lo_mmd_qdum', 'qvco', 100), ('lo_obs', 'qvco', 100), ('lo_obs_q', 'qvco', 100), ('lo_lf', 'qvco', 150),
        ('cdr', 'pll_cdr', 100), ('pll_vreg2', 'isw_pll', 50)]]
else:
    KEEPOUTS = [[r[0] - 5, r[1] - 5, r[2] + 5, r[3] + 5] for v in json.load(open(RUN + '/pads.json'))['pads'].values() for r in v['footprint']]
    MFORBID = {'W': [(3000.0, 3810.0)], 'E': [(3210.0, 3625.0)]}
    RULES = [('digital', 'core_bias', 100), ('aosc', 'por', 300)]
    VIRTUAL = {}
    G4 = {'isw_wired_cap': ('E', 556.5), 'isw_wired_rx': ('E', 2260.0), 'isw_pll': ('E', 4143.5), 'isw_debug': ('W', 2666.5)}
    ADJ = [(a, b, d, 1) for a, b, d in [
        ('ctle', 'pad_hs_rx', 60), ('detect', 'pad_hs_rx', 150), ('detect', 'ctle', 150), ('slicer', 'ctle', 60), ('ptrim', 'slicer', 60), ('pll_cdr', 'ptrim', 80),
        ('pll_tx', 'wiredtx', 150), ('cdr', 'pll_cdr', 100), ('wrx_cap', 'digital', 300), ('wrx_cap', 'slicer', 200), ('cascode_pump', 'pad_wire_tx', 60),
        ('termination', 'pad_hs_rx', 100), ('usb_txdrv', 'pad_usb', 150), ('usb_txdrv', 'wiredtx', 300), ('term_buffer', 'pad_wire_tx', 150),
        ('attached_tx_interlock', 'pad_wire_tx', 150), ('rx_wtx_ext', 'pad_wtx_ext', 100), ('rx_ref_in', 'pad_ref', 150), ('rx_aux_clk', 'pad_aux_clk', 150),
        ('bb_tap_wmon', 'pad_wmon', 100), ('vthdac', 'slicer', 100), ('wordclk_rx', 'wrx_cap', 100), ('pll_vreg2', 'isw_pll', 50)]]
