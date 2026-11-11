"""Full-chip electrical netlist: every placed instance bound to its real subcircuit.

Every port of every instance gets a net and a binding category. Nothing is
silently tied: a port without a defined source becomes `UNBOUND_<inst>_<port>`
and is listed in the report. Control ports whose register field drives them
through decode glue (state -> enable, island_on -> island_off) are bound to the
glue net and the glue requirement is recorded with its register bits.

Outputs: pt_chip_full.spice (structural top + subcircuit library with collision-
checked names), binding.json (per-port net, category, source).
"""
import hashlib
import json
import re
from pathlib import Path

import inventory as inv

PROJECT, ROOT = inv.PROJECT, inv.ROOT

CORE_BIAS_CONSUMER = {
    'lna': 'lna', 'rxmix_i': 'rxmix_i', 'rxmix_q': 'rxmix_q', 'bbfilter_i': 'bbfilter_i', 'bbfilter_q': 'bbfilter_q',
    'txmix_i': 'txmix_i', 'txmix_q': 'txmix_q', 'rfdriver': 'rfdriver', 'adc_i': 'adc_i', 'adc_q': 'adc_q',
    'dac_i': 'dac_i', 'dac_q': 'dac_q', 'refbuf': 'refbuf', 'pll_tx': 'pll_ring_tx', 'pll_cdr': 'pll_ring_rx',
    'pll_host': 'pll_ring_host', 'ctle': 'ctle', 'detect': 'detect', 'wiredtx': 'wiredtx',
    'bb_tap_i': 'bb_tap_i', 'bb_tap_q': 'bb_tap_q', 'bb_tap_wmon': 'bb_tap_wmon'}
# Register 'state' (off/warm/active) or enable field that gates each instance.
ENABLE_FIELD = {
    'lna': 'lna.state.state', 'rxmix_i': 'rxmix_i.state.state', 'rxmix_q': 'rxmix_q.state.state',
    'bbfilter_i': 'rxfilter_i.state.state', 'bbfilter_q': 'rxfilter_q.state.state',
    'txmix_i': 'txmix_i.state.state', 'txmix_q': 'txmix_q.state.state', 'txsum': 'txsum.state.state',
    'rfdriver': 'rfdriver.state.state', 'adc_i': 'adc_i.state.state', 'adc_q': 'adc_q.state.state',
    'dac_i': 'dac_i.state.state', 'dac_q': 'dac_q.state.state', 'refbuf': 'refbuf.state.state',
    'ctle': 'ctle.state.state', 'detect': 'detect.state.state', 'slicer': 'slicer.state.state',
    'termination': 'termination.state.state', 'rxlevel': 'rxlevel.state.state', 'rxselect': 'rxselect.state.state',
    'wiredtx': 'wiredtx.state.state', 'cdr': 'cdr.state.state', 'clockmux': 'clockmux.state.state',
    'pll_tx': 'wirepll.state.state', 'pll_cdr': 'cdr.state.state', 'pll_host': 'rfpll.state.state',
    'hsbias': 'usbhs.bias.enable'}
# Explicit ATB node <- instance port bindings (spec/debug-controls.json atb_nodes).
ATB_PORTS = {
    ('lna', 'atb_nbias'): 'lna_bias', ('lna', 'atb_vdcm'): 'rf_vcm', ('rxmix_i', 'atb_vbp'): 'rxmix_bias',
    ('bbfilter_i', 'atb_vbp'): 'bbfilter_bias', ('bbfilter_i', 'atb_vcm'): 'pga_bias',
    ('txmix_i', 'atb_bias'): 'txmix_bias', ('rfdriver', 'atb_bias'): 'rfdriver_bias',
    ('ctle', 'atb_ctle_pbias'): 'ctle_bias', ('detect', 'atb_det_vref'): 'detect_ibias',
    ('wiredtx', 'ATB_NBIAS'): 'wiredtx_bias', ('termination', 'TERM_VCM'): 'termination_vcm',
    ('pll_tx', 'ATB_VCTRL'): 'pll_vctrl', ('lo_ext', 'ATB_VB'): 'quadrature_bias', ('cdr', 'atb_cdr_pbias'): 'cdr_bias',
    ('adc_i', 'ATB_BIAS'): 'adc_comparator_bias', ('dac_i', 'ATB_BIAS'): 'dac_bias', ('refbuf', 'VREF'): 'conv_vref',
    ('bb_tap_i', 'atb_nbias'): 'debug_buffer_bias', ('hsbias', 'IBIAS'): 'usbhs_ibias',
    ('rx_aux_clk', 'INP'): 'refinput_vcm', ('slicer', 'SL_P'): 'slicer_bias'}
SUPPLY_SENSE = {'core_vdd_sense': 'VDD', 'host_vdd_sense': 'VDD', 'wire_vdd_sw_sense': 'RAIL_wired',
                'rf_vdd_sw_sense': 'RAIL_rf', 'pll_vdd_sw_sense': 'RAIL_pll', 'usb_vdd_sw_sense': 'RAIL_wired',
                'conv_vdd_sw_sense': 'RAIL_conv', 'debug_vdd_sw_sense': 'RAIL_debug', 'vss_local_sense': 'VSS',
                'master_vref0': 'VREF0_CONV', 'conv_vcm': 'VCM_CONV', 'rf_vcm': 'VCM_RF'}
# Signal paths between payload blocks and pads (instance.port -> net).
PATHS = {
    # RF receive: pad -> LNA -> I/Q mixers -> shared baseband -> ADC
    'lna.rf_in_p': 'RF_RX_P', 'lna.rf_in_n': 'RF_RX_N', 'lna.rf_out_p': 'RFA_P', 'lna.rf_out_n': 'RFA_N',
    'rxmix_i.rf_p': 'RFA_P', 'rxmix_i.rf_n': 'RFA_N', 'rxmix_q.rf_p': 'RFA_P', 'rxmix_q.rf_n': 'RFA_N',
    'rxmix_i.lo_p': 'LO_IP', 'rxmix_i.lo_n': 'LO_IN', 'rxmix_q.lo_p': 'LO_QP', 'rxmix_q.lo_n': 'LO_QN',
    'rxmix_i.bb_p': 'BBI_RX_P', 'rxmix_i.bb_n': 'BBI_RX_N', 'rxmix_q.bb_p': 'BBQ_RX_P', 'rxmix_q.bb_n': 'BBQ_RX_N',
    'bbfilter_i.rx_in_p': 'BBI_RX_P', 'bbfilter_i.rx_in_n': 'BBI_RX_N', 'bbfilter_q.rx_in_p': 'BBQ_RX_P', 'bbfilter_q.rx_in_n': 'BBQ_RX_N',
    'bbfilter_i.out_rx_p': 'ADCI_P', 'bbfilter_i.out_rx_n': 'ADCI_N', 'bbfilter_q.out_rx_p': 'ADCQ_P', 'bbfilter_q.out_rx_n': 'ADCQ_N',
    'adc_i.INP': 'ADCI_P', 'adc_i.INN': 'ADCI_N', 'adc_q.INP': 'ADCQ_P', 'adc_q.INN': 'ADCQ_N',
    'adc_i.VREF': 'VREF_CONV', 'adc_q.VREF': 'VREF_CONV', 'refbuf.VREF': 'VREF_CONV', 'refbuf.VREF0': 'VREF0_CONV',
    'adc_i.VCM': 'VCM_CONV', 'adc_q.VCM': 'VCM_CONV',
    # RF transmit: DAC -> shared baseband (TX direction) -> TX mixers -> sum -> driver -> pad
    'dac_i.OUTP': 'DACI_P', 'dac_i.OUTN': 'DACI_N', 'dac_q.OUTP': 'DACQ_P', 'dac_q.OUTN': 'DACQ_N',
    'bbfilter_i.tx_in_p': 'DACI_P', 'bbfilter_i.tx_in_n': 'DACI_N', 'bbfilter_q.tx_in_p': 'DACQ_P', 'bbfilter_q.tx_in_n': 'DACQ_N',
    'bbfilter_i.out_tx_p': 'BBI_TX_P', 'bbfilter_i.out_tx_n': 'BBI_TX_N', 'bbfilter_q.out_tx_p': 'BBQ_TX_P', 'bbfilter_q.out_tx_n': 'BBQ_TX_N',
    'txmix_i.bb_p': 'BBI_TX_P', 'txmix_i.bb_n': 'BBI_TX_N', 'txmix_q.bb_p': 'BBQ_TX_P', 'txmix_q.bb_n': 'BBQ_TX_N',
    'txmix_i.dac_p': 'DACI_P', 'txmix_i.dac_n': 'DACI_N', 'txmix_q.dac_p': 'DACQ_P', 'txmix_q.dac_n': 'DACQ_N',
    'txmix_i.lo_p': 'LO_IP', 'txmix_i.lo_n': 'LO_IN', 'txmix_q.lo_p': 'LO_QP', 'txmix_q.lo_n': 'LO_QN',
    'txmix_i.out_p': 'TXI_P', 'txmix_i.out_n': 'TXI_N', 'txmix_q.out_p': 'TXQ_P', 'txmix_q.out_n': 'TXQ_N',
    'txsum.i_p': 'TXI_P', 'txsum.i_n': 'TXI_N', 'txsum.q_p': 'TXQ_P', 'txsum.q_n': 'TXQ_N',
    'txsum.out_p': 'TXS_P', 'txsum.out_n': 'TXS_N', 'rfdriver.in_p': 'TXS_P', 'rfdriver.in_n': 'TXS_N',
    'rfdriver.pad_p': 'RF_TX_P', 'rfdriver.pad_n': 'RF_TX_N',
    # Baseband debug taps (BB_I/BB_Q pads; WMON)
    'bb_tap_i.pad_p': 'BB_I_P', 'bb_tap_i.pad_n': 'BB_I_N', 'bb_tap_q.pad_p': 'BB_Q_P', 'bb_tap_q.pad_n': 'BB_Q_N',
    'bb_tap_i.in_p': 'ADCI_P', 'bb_tap_i.in_n': 'ADCI_N', 'bb_tap_q.in_p': 'ADCQ_P', 'bb_tap_q.in_n': 'ADCQ_N',
    'bb_tap_i.inj_p': 'DACI_P', 'bb_tap_i.inj_n': 'DACI_N', 'bb_tap_q.inj_p': 'DACQ_P', 'bb_tap_q.inj_n': 'DACQ_N',
    'bb_tap_wmon.pad_p': 'WMON', 'bb_tap_wmon.pad_n': 'VSS', 'bb_tap_wmon.in_p': 'WMON_IN', 'bb_tap_wmon.in_n': 'VCM_WIRE',
    'bb_tap_wmon.inj_p': 'VCM_WIRE', 'bb_tap_wmon.inj_n': 'VCM_WIRE',
    # LO: external passive I/Q (REF_IN / AUX_CLK) or internal -> lo_ext -> mixers
    'lo_ext.EXT_IP': 'REF_IN', 'lo_ext.EXT_IN': 'REF_IN_N', 'lo_ext.EXT_QP': 'AUX_CLK_P', 'lo_ext.EXT_QN': 'AUX_CLK_N',
    'lo_ext.LOI_IP': 'LOI_IP', 'lo_ext.LOI_IN': 'LOI_IN', 'lo_ext.LOI_QP': 'LOI_QP', 'lo_ext.LOI_QN': 'LOI_QN',
    'polyphase.LOI_IP': 'LOI_IP', 'polyphase.LOI_IN': 'LOI_IN', 'polyphase.LOI_QP': 'LOI_QP', 'polyphase.LOI_QN': 'LOI_QN',
    'lo_ext.LO_IP': 'LO_IP', 'lo_ext.LO_IN': 'LO_IN', 'lo_ext.LO_QP': 'LO_QP', 'lo_ext.LO_QN': 'LO_QN',
    # Reference and debug clock receivers
    'rx_aux_clk.INP': 'AUX_CLK_P', 'rx_aux_clk.INN': 'AUX_CLK_N', 'rx_wclk_in.INP': 'WCLK_IN_P', 'rx_wclk_in.INN': 'WCLK_IN_N',
    'rx_wtx_ext.INP': 'WTX_EXT_P', 'rx_wtx_ext.INN': 'WTX_EXT_N', 'rx_wtx_ext.OUTP': 'WTX_EXT_DATA',
    'rx_aux_clk.OUTP': 'AUX_CK', 'rx_wclk_in.OUTP': 'WCK_EXT',
    'rx_aux_clk.EN': 'rx_en_aux', 'rx_wclk_in.EN': 'rx_en_wclk', 'rx_wtx_ext.EN': 'rx_en_wtx_ext',
    # Clock observation outputs to pt_debug_physical
    'clk_obs.OUT': 'clk_obs', 'wclk_obs.OUT': 'wclk_obs',
    # Wired RX: pad -> termination/rxlevel (in pad family) -> rxselect/ctle -> slicer
    'ctle.RX_P': 'WRX_P', 'ctle.RX_N': 'WRX_N', 'ctle.CTLE_P': 'CTLE_P', 'ctle.CTLE_N': 'CTLE_N',
    'rxselect.RX_P': 'WRX_P', 'rxselect.RX_N': 'WRX_N', 'rxselect.CTLE_P': 'CTLE_P', 'rxselect.CTLE_N': 'CTLE_N',
    'rxselect.SL_P': 'SL_P', 'rxselect.SL_N': 'SL_N', 'slicer.SL_P': 'SL_P', 'slicer.SL_N': 'SL_N',
    'detect.RX_P': 'WRX_P', 'detect.RX_N': 'WRX_N', 'detect.TX_P': 'WIRE_TX_P', 'detect.TX_N': 'WIRE_TX_N',
    'wmon_sel.RX_P': 'WRX_P', 'wmon_sel.RX_N': 'WRX_N', 'wmon_sel.CTLE_P': 'CTLE_P', 'wmon_sel.CTLE_N': 'CTLE_N',
    'wmon_sel.WMON_IN': 'WMON_IN',
    'termination.TERM_ENABLE': 'TERM_ENABLE', 'termination.DIFF_ENABLE': 'DIFF_ENABLE', 'termination.TERM_VCM': 'TERM_VCM',
    'rxlevel.DIV_ENABLE': 'DIV_ENABLE', 'rxlevel.BYPASS_ENABLE': 'BYPASS_ENABLE',
    # Wired TX: serializer/driver commands -> txpad; external data fallback
    'wiredtx.CMD_MAIN_P': 'TX_MAIN_P', 'wiredtx.CMD_MAIN_N': 'TX_MAIN_N', 'wiredtx.CMD_POST_P': 'TX_POST_P',
    'wiredtx.CMD_POST_N': 'TX_POST_N', 'wiredtx.CMD_TMDS_P': 'TX_TMDS_P', 'wiredtx.CMD_TMDS_N': 'TX_TMDS_N',
    'wiredtx.MAIN_BIAS': 'TX_MAIN_BIAS', 'wiredtx.POST_BIAS': 'TX_POST_BIAS', 'wiredtx.TMDS_BIAS': 'TX_TMDS_BIAS',
    'wiredtx.WTX_EXT_DATA': 'WTX_EXT_DATA',
    'wiredtx.WORD_CLK': 'ct_word_clk', 'wiredtx.SER_EN': 'ct_ser_run',
    # USB HS bias DAC (0xD7) -> wirepad HS gate bias
    'hsbias.HS_PBIAS': 'HS_PBIAS',
    # Clock tree
    'pll_tx.REF': 'ref_clk', 'pll_cdr.REF': 'ref_clk', 'pll_host.REF': 'ref_clk',
    'prescale.CK_OUT': 'ct_wclk', 'wordclk.WORD_CLK': 'ct_word_clk',
    'pll_tx.FBCK': 'fc_src[0]', 'pll_cdr.FBCK': 'fc_src[1]', 'ring_osc.OUT': 'fc_src[2]', 'vco_replica.OUT': 'fc_src[3]',
    'aosc.CLK': 'fc_src[4]', 'pll_tx.LOCK': 'analog_status[0]',
    # pt_pll_ring r9 (AC3-W11): non-CDR ring instances tie the CDR fast-tune / N5 / N10 pins low
    **{f'{i}.{p}': 'VSS' for i in ('pll_tx', 'pll_host') for p in ('N5', 'N10', 'KP0', 'KP1', 'KP2', 'FU0', 'FU1', 'FU2', 'FU3',
                                                               'FD0', 'FD1', 'FD2', 'FD3')},
    'cdr.VCTRL': 'CDR_VCTRL', 'cdr.FBCK_IN': 'fc_src[1]', 'cdr.REF_IN': 'ref_clk', 'cdr.freq_hold': 'cdr_freq_locked',
    # POR (cold start; RESET_N supervisor covers slow ramps, board B1)
    'por.vdd3v3': 'VDD', 'por.vss': 'VSS', 'por.ena': 'VDD', 'por.porb': 'por_n', 'por.por': 'POR_HIGH',
    'por.por_unbuf': 'POR_UNBUF',
    # Bring-up fallback control (pt_wtx_fallback_control) on the wired rail
    'wtx_fallback_control.RAIL_wired': 'RAIL_wired', 'wtx_fallback_control.ISO_wired': 'ISO_wired',
    'wtx_fallback_control.WIRED_ON': 'island_on[0]',
}
PAD_PORTS = {   # pad family port -> net (per custom pad instance; P/N handled from inventory)
    'wirepad': {'VDD': 'RAIL_wired', 'TERM_VCM': 'TERM_VCM', 'TERM_ENABLE': 'TERM_ENABLE', 'DIFF_ENABLE': 'DIFF_ENABLE',
                'DIV_ENABLE': 'DIV_ENABLE', 'BYPASS_ENABLE': 'BYPASS_ENABLE', 'RX_P': 'WRX_P', 'RX_N': 'WRX_N',
                'HS_PBIAS': 'HS_PBIAS'},
    'txpad': {'VDD': 'RAIL_wired', 'MAIN_P': 'TX_MAIN_P', 'MAIN_N': 'TX_MAIN_N', 'MAIN_BIAS': 'TX_MAIN_BIAS',
              'POST_P': 'TX_POST_P', 'POST_N': 'TX_POST_N', 'POST_BIAS': 'TX_POST_BIAS', 'TMDS_P': 'TX_TMDS_P',
              'TMDS_N': 'TX_TMDS_N', 'TMDS_BIAS': 'TX_TMDS_BIAS'},
    'refpad': {'VCM': 'REF_VCM'},
}


def subckts(text):
    text = re.sub(r'\n\+\s*', ' ', text)
    out = {}
    for m in re.finditer(r'^\.subckt\s+(\S+)(.*?)^\.ends\b[^\n]*', text, re.M | re.S | re.I):
        out[m.group(1)] = m.group(0)
    return out


def ports_of(body):
    head = body.splitlines()[0].split()
    return [p for p in head[2:] if '=' not in p]


def build(work, fp, have_wrx_cap):
    work = Path(work)
    regmap = json.loads((PROJECT/'spec/register-map.json').read_text())
    fields = {f['name']: f for f in regmap['fields']}
    controls = json.loads((PROJECT/'spec/debug-controls.json').read_text())
    library = {}
    origin = {}
    collisions = []
    used_files = {}

    def load(path, keep=()):
        path = ROOT/path
        text = path.read_text()
        used_files[str(path.relative_to(ROOT))] = hashlib.sha256(text.encode()).hexdigest()
        # Extracted netlists reuse leaf names with instance-specific parasitics: give every
        # non-top subcircuit of this file a file-unique prefix before merging the library.
        tag = re.sub(r'\W', '_', path.parent.name+'_'+path.stem)
        for name in list(subckts(text)):
            if name not in keep:
                text = re.sub(r'(?<![\w.])'+re.escape(name)+r'(?![\w.])', f'{tag}__{name}', text)
        subs = subckts(text)
        for name, body in subs.items():
            if name in library and library[name] != body and name not in [v[3] for v in inv.PAD_FAMILIES.values()]:
                collisions.append(dict(subckt=name, first=origin[name], second=str(path.relative_to(ROOT))))
                continue
            library[name] = body
            origin[name] = str(path.relative_to(ROOT))
        return subs

    master_ports = {}
    missing_netlist = []
    for m, (gds, top, sp, sub, isl) in inv.MASTERS.items():
        if m == 'core_bias' or sp is None or (m == 'wrx_cap' and not have_wrx_cap):
            continue
        subs = load(sp, keep=(sub,))
        if sub not in subs:
            missing_netlist.append(f'{m}: {sp} has no .subckt {sub} at run time')
            continue
        master_ports[m] = ports_of(subs[sub])
    # pt_core_bias from the maintained builder (integration/core_bias.py)
    import sys
    sys.path.insert(0, str(PROJECT/'integration'))
    sys.path.insert(0, str(PROJECT/'verification'))
    import core_bias
    cb = core_bias.build(lambda p: Path(p).read_text())
    for name, body in subckts(cb['text']).items():
        if name not in library:
            library[name] = body
            origin[name] = 'integration/core_bias.py'
    master_ports['core_bias'] = cb['pins']
    for fam, (gds, top, sp, sub) in inv.PAD_FAMILIES.items():
        subs = load(sp, keep=(sub,))
        master_ports['pad_'+fam] = ports_of(subs[sub])
        library['pad_'+fam] = re.sub(r'^(\.subckt\s+)'+re.escape(sub)+r'\b', r'\g<1>pad_'+fam, subs[sub], flags=re.M)
        library['pad_'+fam] = re.sub(r'(\.ends\s+)'+re.escape(sub)+r'\b', r'\g<1>pad_'+fam, library['pad_'+fam])
    master_ports['pad_single_leg_b'] = master_ports['pad_single_leg']
    dig = json.loads((work/'digital.json').read_text())
    digital_ports = sorted(dig['pins'], key=lambda s: (re.sub(r'\[\d+\]', '', s), int(re.search(r'\[(\d+)\]', s).group(1)) if '[' in s else -1))
    master_ports['pt_digital_macro'] = digital_ports

    island_of = {p['name']: p['island'] for p in fp['placed']}
    master_of = {p['name']: p['master'] for p in fp['placed']}
    bindings = {}
    glue = {}
    unbound = []

    def field_bits(name):
        f = fields.get(name)
        if not f or f['bus_lsb'] is None:
            return None
        w = f.get('bus_bits', f['bits'])
        return [f'{f["bus"]}_cfg[{f["bus_lsb"]+k}]' for k in range(w)]

    def bind(inst, port, net, cat, src=None):
        bindings.setdefault(inst, {})[port] = dict(net=net, category=cat, **({'source': src} if src else {}))

    atb_node_net = {}
    for (i, p), node in ATB_PORTS.items():
        atb_node_net[node] = f'{i}.{p}'
    for inst, master in master_of.items():
        if master.startswith('attached_tx_') or master.startswith('atb_') or master == 'core_bias':
            continue
        isl = island_of[inst]
        rail = 'VDD' if isl == 'core' else f'RAIL_{isl}'
        for port in master_ports.get(master, []):
            key = f'{inst}.{port}'
            up = port.upper()
            if key in PATHS:
                bind(inst, port, PATHS[key], 'signal_path')
            elif (inst, port) in ATB_PORTS:
                bind(inst, port, 'ATBN_'+ATB_PORTS[(inst, port)], 'atb_node')
            elif up in ('VDD', 'VDD_WIRE_SW', 'VDD_PLL_SW', 'AVDD', 'DVDD', 'VDD3V3') and not master.startswith('isw_'):
                bind(inst, port, rail, 'supply')
            elif up in ('VSS', 'DVSS', 'AVSS'):
                bind(inst, port, 'VSS', 'supply')
            elif master.startswith('isw_'):
                n = master[4:]
                b = inv.ISLAND_BIT[n]
                net = dict(VDD='VDD', VISL=f'RAIL_{n}', EN=f'island_en[{b}]', ISO=f'ISO_{n}', PG=f'island_pgood[{b}]')[up]
                bind(inst, port, net, 'island_switch')
            elif up == 'IBIAS' and inst in CORE_BIAS_CONSUMER:
                bind(inst, port, 'BIAS_'+CORE_BIAS_CONSUMER[inst], 'core_bias_output')
            elif up in ('EN', 'CDR_EN', 'CTLE_EN', 'DET_EN', 'SLICER_EN', 'TERM_EN', 'RXLEVEL_EN', 'RXSELECT_EN',
                        'WMON_EN', 'EN_MAIN') and inst in ENABLE_FIELD:
                f = ENABLE_FIELD[inst]
                bits = field_bits(f)
                net = f'EN_EFF_{inst}'
                if f == 'usbhs.bias.enable' and bits:
                    bind(inst, port, bits[0], 'register_bit', f)
                elif bits:
                    glue[net] = dict(kind='state_active_decode', field=f, bits=bits, island_on=f'island_on[{inv.ISLAND_BIT.get(isl, -1)}]' if isl in inv.ISLAND_BIT else None)
                    bind(inst, port, net, 'decoded_enable', f)
                else:
                    unbound.append(dict(inst=inst, port=port, reason=f'no register field {f}'))
                    bind(inst, port, f'UNBOUND_{inst}_{port}', 'unbound')
            elif up in ('ISLAND_OFF',):
                glue[f'ISLAND_OFF_{isl}'] = dict(kind='inverter', input=f'island_on[{inv.ISLAND_BIT[isl]}]')
                bind(inst, port, f'ISLAND_OFF_{isl}', 'decoded_enable')
            elif inst == 'hsbias' and re.fullmatch(r'C(\d)', port):
                k = int(port[1:])
                bits = field_bits('usbhs.bias.code')
                bind(inst, port, bits[k], 'register_bit', 'usbhs.bias.code')
            else:
                bind(inst, port, f'UNBOUND_{inst}_{port}', 'unbound')
                unbound.append(dict(inst=inst, port=port, reason='no binding rule (control decode / datapath not defined)'))
    # core bias: consumers' enables and outputs (integration/core_bias.py contract)
    for port in master_ports['core_bias']:
        if port in ('VDD', 'VSS'):
            bind('core_bias', port, port, 'supply')
        elif port.startswith('RAIL_'):
            bind('core_bias', port, port, 'island_rail')
        elif port.startswith('ON_'):
            bind('core_bias', port, f'island_on[{inv.ISLAND_BIT[port[3:]]}]', 'digital')
        elif port in cb['control_bindings']:
            bind('core_bias', port, cb['control_bindings'][port], 'register_bit')
        elif port.startswith('BIAS_'):
            c = port[5:]
            users = [i for i, cc in CORE_BIAS_CONSUMER.items() if cc == c and i in master_of]
            bind('core_bias', port, port if users else f'UNBOUND_core_bias_{port}', 'core_bias_output' if users else 'unbound')
            if not users:
                unbound.append(dict(inst='core_bias', port=port, reason=f'no placed consumer {c}'))
        elif port.startswith('EN_'):
            c = port[3:]
            users = [i for i, cc in CORE_BIAS_CONSUMER.items() if cc == c and i in master_of]
            if users:
                bind('core_bias', port, f'EN_EFF_{users[0]}', 'decoded_enable')
            else:
                bind('core_bias', port, f'UNBOUND_core_bias_{port}', 'unbound')
                unbound.append(dict(inst='core_bias', port=port, reason=f'no placed consumer {c}'))
        elif port in cb['observation_bindings'].values():
            node = {v: k for k, v in cb['observation_bindings'].items()}[port]
            nn = next(n['name'] for n in controls['atb_nodes'] if n['code'] == node)
            bind('core_bias', port, 'ATBN_'+nn, 'atb_node')
        else:
            bind('core_bias', port, f'UNBOUND_core_bias_{port}', 'unbound')
            unbound.append(dict(inst='core_bias', port=port, reason='VGEN outputs have no consumer'))
    # ATB tree: one leaf per node; node ports to the bound node nets
    node_bound = {}
    for b in bindings.values():
        for v in b.values():
            if v['net'].startswith('ATBN_'):
                node_bound[v['net'][5:]] = True
    for n, net in SUPPLY_SENSE.items():
        node_bound[n] = net
    nodes = {n['code']: n['name'] for n in controls['atb_nodes'] if n.get('hardware', True)}
    for inst, master in master_of.items():
        if master in ('atb_leaf_s', 'atb_leaf_f'):
            bus = 0 if master == 'atb_leaf_f' else 1
            code = int(inst.split('leaf')[1])
            name = nodes[code]
            grp = next(gi for gi, g in enumerate(controls['atb_groups'][f'atb{bus}']) if code in g['codes'])
            node_net = SUPPLY_SENSE.get(name, 'ATBN_'+name)
            if name not in node_bound:
                node_net = f'UNBOUND_atbnode_{name}'
                unbound.append(dict(inst=inst, port='NODE', reason=f'ATB node {name} has no physical source bound (characterization or unassigned)'))
            for port, net in dict(NODE=node_net, BUS=f'ATB{bus}_LOCAL{grp}', SEL=f'atb{bus}_sw[{code-1}]', VDD='VDD', VSS='VSS').items():
                bind(inst, port, net, 'atb_tree')
        elif master == 'atb_grp':
            bus, gi = int(inst[3]), int(inst.split('grp')[1])
            for port, net in dict(NODE=f'ATB{bus}_LOCAL{gi}', BUS=f'ATB{bus}_GLOBAL', SEL=f'atb{bus}_grp[{gi}]', VDD='VDD', VSS='VSS').items():
                bind(inst, port, net, 'atb_tree')
        elif master == 'atb_pad':
            bus = int(inst[3])
            for port, net in dict(PAD=f'ATB{bus}', BUS=f'ATB{bus}_GLOBAL', SEL=f'atb{bus}_en', VDD='VDD', VSS='VSS').items():
                bind(inst, port, net, 'atb_tree')
    # custom pad families
    for name, fam, edge, origin_site, sites, (pn, nn), rep in inv.CUSTOM_PADS:
        famkey = 'single_leg' if fam == 'single_leg_b' else fam
        for port in master_ports['pad_'+famkey]:
            if port == 'PAD_P':
                net = pn
            elif port == 'PAD_N':
                net = nn or 'VSS'
            elif port == 'VSS':
                net = 'VSS'
            elif port == 'ESD_RAIL':
                net = f'ESD_RAIL_{name}'
                for a_, b_ in inv.SHARED_PROTECTION:
                    if name in (a_, b_):
                        net = f'ESD_RAIL_{a_}'      # shared through the 40 um buses
            elif port == 'ATB_ESD_RAIL':
                net = f'ATB_ESD_RAIL_{name}'
            elif port in PAD_PORTS.get(fam, {}):
                net = PAD_PORTS[fam][port]
            else:
                net = f'UNBOUND_{name}_{port}'
                unbound.append(dict(inst=name, port=port, reason='pad attachment control not bound'))
            bind(name, port, net, 'pad')
    # digital macro: every port on the pt_chip.sv net of the same name
    for port in digital_ports:
        bind('digital', port, port, 'digital')
    # nets with exactly one connection (excluding pads/supplies) are dangling
    count = {}
    for inst, b in bindings.items():
        for port, v in b.items():
            count.setdefault(v['net'], []).append(f'{inst}.{port}')
    dangling = sorted(n for n, users in count.items() if len(users) == 1 and not n.startswith('UNBOUND')
                      and n not in ('VDD', 'VSS') and not n.startswith(('RAIL_',)))
    # write the netlist
    lines = ['* pt_chip_full: generated by verification/run_chip_assembly.py stage 6 (chip_assembly/netlist.py)',
             '* Subcircuit library: extracted/pex netlists of every placed master (sha256 in binding.json).',
             '* pt_digital_macro is a black box (abstract only); glue nets EN_EFF_* / ISLAND_OFF_* need decode cells.']
    lines += [library[k] for k in sorted(library)]
    lines.append('.subckt pt_digital_macro '+' '.join(digital_ports)+'\n.ends pt_digital_macro')
    chip_ports = sorted({v['net'] for b in bindings.values() for v in b.values()} & set(
        [p[5][0] for p in inv.CUSTOM_PADS]+[p[5][1] for p in inv.CUSTOM_PADS if p[5][1]]+['ATB0', 'ATB1']))
    lines.append('.subckt pt_chip_full VDD VSS '+' '.join(chip_ports))
    sub_of = {m: v[3] for m, v in inv.MASTERS.items()}
    for inst, b in sorted(bindings.items()):
        master = 'pt_digital_macro' if inst == 'digital' else (master_of.get(inst) or
                 next(('pad_'+('single_leg' if p[1] == 'single_leg_b' else p[1])) for p in inv.CUSTOM_PADS if p[0] == inst))
        sub = sub_of.get(master, master)
        order = master_ports[master] if master in master_ports else master_ports[master_of[inst]]
        lines.append('X'+inst+' '+' '.join(b[p]['net'] for p in order)+' '+sub)
    for d in fp['decaps']:
        net = 'VDD' if d['island'] == 'core' else 'RAIL_'+d['island']
        for k in range(d['units']):
            lines.append(f"XC{d['name']}_{k} {net} VSS cap_mim_2f0_m4m5_noshield c_width={inv.MIM_UNIT_UM:g}u c_length={inv.MIM_UNIT_UM:g}u")
    lines.append('.ends pt_chip_full')
    (work/'pt_chip_full.spice').write_text('\n'.join(lines)+'\n')
    cats = {}
    for b in bindings.values():
        for v in b.values():
            cats[v['category']] = cats.get(v['category'], 0)+1
    hs = bindings.get('hsbias', {})
    # Expected bits from the generated RTL defines (independent of the register-map JSON the binder used).
    defs = (PROJECT/'rtl/pt_regmap_defs.svh').read_text()
    def _lsb(name):
        m = re.search(r'`define\s+'+name+r'\s+(\d+)', defs)
        return int(m.group(1)) if m else None
    code_lsb, en_lsb = _lsb('PT_A_USBHS_BIAS__CODE_LSB'), _lsb('PT_A_USBHS_BIAS__ENABLE_LSB')
    def _hs_ok(h, c0, e0):
        return (c0 is not None and e0 is not None and
                all(h.get(f'C{k}', {}).get('net') == f'analog_cfg[{c0+k}]' for k in range(8)) and
                h.get('EN', {}).get('net') == f'analog_cfg[{e0}]')
    hs_ok = _hs_ok(hs, code_lsb, en_lsb)
    hs_negative_control = not _hs_ok(hs, code_lsb+1 if code_lsb is not None else None, en_lsb)   # off-by-one must fail
    placed_unbound_inst = sorted(set(m for m in master_of.values() if m not in master_ports and not m.startswith('attached_tx_')))
    res = dict(ok=not collisions, masters_missing_netlist=missing_netlist, instances=len(bindings), ports=sum(len(b) for b in bindings.values()),
               categories=cats, unbound_ports=len(unbound), dangling_nets=len(dangling),
               glue_nets=len(glue), subckt_name_collisions=collisions, usb_hs_bias_0xD7_bound=hs_ok, usb_hs_bias_expected_lsb=dict(code=code_lsb, enable=en_lsb),
               usb_hs_bias_negative_control_detected=hs_negative_control,
               masters_without_netlist=placed_unbound_inst + ['attached_tx_* (pad attachment cells; netlist inside txpad family LVS only)'],
               library_subckts=len(library))
    (work/'binding.json').write_text(json.dumps(dict(summary=res, bindings=bindings, unbound=unbound, glue=glue,
                                                     dangling=dangling, files=used_files), indent=1))
    return res
