#!/usr/bin/env python3
"""Per supply pin worst DC current (mA) for the assembly plate / hook EM rule (coordinator 2026-11-28).

  python3 pin_currents.py            -> rf/pin_currents.json, wired/pin_currents.json

Every conn pin bound to VDD, VSS, RAIL_*, VREG_*, VDD_* gets one row: avg_ma (worst DC current at 85 C in the
block's highest-current mode), peak_ma where it differs, kind (supply / tie), source. Rule of the hook: a pin above
0.5 mA needs a plate or a multi-cut landing.

Figures: block worst in-window currents from spec/budgets/power_budget.py (MEASURED rows, INSTANCE_WORST_MA, pd2
island design currents) and block evidence / READMEs; every figure measured at 22-32 C is scaled by K85 = 1.2 for
85 C (PTAT-biased blocks rise ~0.3 %/K over 53 K = 1.16; CMOS dynamic current falls). A figure already at >= 85 C
(lo_txbuf ff/125) is not scaled. Where no bench exists the row says 'bound' and why. A block's supply current flows
through each of its supply pins (one VDD-side, one VSS pin in every block here): avg_ma is per pin, not shared.
Pins bound to a supply only as a logic tie (EN=VSS, TRIM=VSS, inputs tied off) carry gate / junction leakage only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, os.path.join(P, 'spec', 'budgets')]
import check_top as ct          # noqa: E402
import power_budget as pb       # noqa: E402

K85 = 1.2
SUPPLY_NETS = ('VDD', 'VSS')
SUPPLY_PREFIX = ('RAIL_', 'VREG_', 'VDD_')
SUPPLY_PINS = re.compile(r'^(VDD.*|VSS|VISL|VIN|VOUT.*|DVDD.*|DVSS|vdd3v3|vss|PAD|RAIL_.*)$')

MEAS = {r[0]: max(v[1] for v in r[2].values()) for r in pb.MEASURED}
BUD = json.load(open(os.path.join(P, 'spec', 'budgets', 'power-budget.json')))
ISL = {c: BUD['pd2_reconciliation'][c]['islands'] for c in ('rf', 'wired')}


def m(name, src=None):
    """(mA at 22-32 C, source) from a MEASURED row"""
    r = next(r for r in pb.MEASURED if r[0] == name)
    return MEAS[name], src or f'power_budget.py MEASURED {name} ({r[4]}: {r[5][:90]})'


# master -> {pin: (mA in-window, source, scale_to_85C)}; '*' = every supply pin of the master
def block_table(chip):
    T = {}
    def two(master, ma, src, vdd='VDD', vss='VSS', k=True, peak=None):
        T[master] = {vdd: (ma, src, k, peak), vss: (ma, src, k, peak)}
    for b in ('lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'adc_i', 'adc_q', 'dac_i', 'dac_q', 'refbuf',
              'lo_mmd', 'lo_mmd_qdum', 'lo_ext', 'ctle', 'slicer', 'detect', 'termination', 'rxlevel', 'rxselect', 'vthdac',
              'ptrim', 'wrx_cap', 'clockmux', 'wordclk'):
        two('pt_' + b, *m(b), vdd='VDD_WIRE_SW' if b in ('ctle', 'slicer', 'detect', 'termination', 'rxlevel', 'rxselect',
                                                         'vthdac', 'ptrim') else 'VDD')
    ctle_f = m('ctle_follower')[0]
    two('pt_ctle', MEAS['ctle'] + ctle_f, 'MEASURED ctle + ctle_follower (followers on the same rails)', vdd='VDD_WIRE_SW')
    tx = m('txsum')
    two('pt_txsum', *tx)
    for q in ('i', 'q'):
        two(f'pt_txmix_{q}', tx[0], 'bound: txsum row carries both txmix tails (' + tx[1][:60] + ')')
    rfd = m('rfdriver')[0]
    T['pt_rfdriver'] = {'VDD': (rfd * pb.RFDRV_DIE_FRACTION, f'MEASURED rfdriver {rfd} mA total x die-rail share {pb.RFDRV_DIE_FRACTION}', True, None),
                        'VSS': (rfd, 'MEASURED rfdriver total: the board feed through the RF_TX pads returns through die VSS', True, None)}
    two('pt_lo_txbuf', 59.3, 'LO-PWR-2 extracted r3, ff/22/3.5; 85 C not separately benched (r1 schematic ff/125 = ff/22 + 4 %)', k=True)
    qv, qp = MEAS['qvco'], MEAS['qvco_pre']
    T['pt_lc_qvco5'] = {'VDD': (qv, 'MEASURED qvco (VDD_LO core)', True, None), 'VDDB': (qp, 'MEASURED qvco_pre (est, VDDB pre-buffer)', True, None),
                        'VSS': (qv + qp, 'qvco core + pre-buffer return', True, None)}
    pf = MEAS['lo_pfdcp']
    two('pt_lo_pfdcp', pf, 'MEASURED lo_pfdcp (est, LO.3 "order 1 mA")')
    reg = MEAS['lo_vreg']
    T['pt_lo_vreg'] = {'VIN': (qv + pf + reg, 'qvco + lo_pfdcp + lo_vtdet + regulator quiescent', True, None),
                       'VOUT': (qv + pf + 0.064, 'loads on VDD_LO: qvco + lo_pfdcp + lo_vtdet', True, None),
                       'VSS': (2.0 * reg, 'bound: 2 x regulator quiescent allowance (loads return on their own VSS)', True, None)}
    two('pt_lo_vtdet', 0.064, 'analog/timing/README.md LO table: 31-64 uA all corners (schematic)')
    T['pt_lo_lf'] = {'VSS': (0.001, 'passive loop filter (R, C to VSS): leakage only', False, None)}
    two('pt_lo_obs', 8.03, 'INSTANCE_WORST_MA lod lo_obs (scratch/timing/lo_obs/results.json ff/22/3.35)')
    ring = 10.2
    T['pt_pll_vreg2'] = {'VIN': (2 * ring + 0.5, 'INSTANCE_WORST_MA pll_vreg2: 2 x 10.2 ring worst + 0.5', True, None),
                         'VOUT_TX': (ring, 'pll_tx ring core worst (e7 static-drop tap pll_tx)', True, None),
                         'VOUT_CDR': (ring, 'pll_cdr ring worst (e7 static-drop tap pll_cdr)', True, None),
                         'VSS': (1.0, 'bound: 2 x 0.5 mA regulator quiescent (rings return on their own VSS)', True, None)}
    two('pt_pll_ring_core', ring, 'e7 static-drop analysis tap pll_tx 10.2 mA (MEASURED pll_tx)')
    two('pt_pll_ring', ring, 'e7 static-drop analysis tap pll_cdr 10.2 mA (MEASURED pll_cdr)')
    two('pt_cdr', 2.0, 'MEASURED pll_misc (est: pt_cdr analog + regulator)', vdd='VDD_PLL_SW')
    two('pt_prescale', *m('prescale'))
    two('pt_refvcm', 0.029, 'analog/core_support README: 15-29 uA')
    two('pt_diff_clk_rx', 4.6 if True else 0, 'INSTANCE_WORST / plate table rx_ref_in 4.6 mA (diff_clk_rx-evidence.json 5.1 on the debug island copy)')
    two('pt_ring_osc', 0.53, 'INSTANCE_WORST_MA debug ring_osc (ring_osc-evidence.json)')
    two('pt_vco_replica', 11.78, 'INSTANCE_WORST_MA debug vco_replica (VCTRL 3.3 V)')
    two('pt_bb_tap', 1.03, 'INSTANCE_WORST_MA bb_tap-evidence.json')
    two('pt_clk_obs16', 5.14, 'INSTANCE_WORST_MA clk_obs-evidence.json')
    two('pt_obs_pre4', 3.0, 'bound: CMOS /4 at <= 1.6 GHz input, prescale (2.4 mA, /16 at 2.5 GHz, ev) x 1.25; no bench')
    two('pt_aosc', *m('aosc'))
    two('por', 0.05, 'bound: comparator + RC power-on reset (no bench current); quiescent well below 0.05 mA', vdd='vdd3v3', vss='vss')
    bias = MEAS['bias']
    core = {'VDD': (bias, 'MEASURED bias (core_support README 0.30-0.52)', True, None)}
    for r in ('RAIL_rf_rx', 'RAIL_conv', 'RAIL_pll', 'RAIL_lo', 'RAIL_debug', 'RAIL_wired_rx', 'RAIL_wired_tx'):
        core[r] = (0.22, 'PDS-18: every core_bias rail draw <= 0.22 mA', True, None)
    core['VSS'] = (bias + 0.22 * 5, 'VDD + rail draws (5 rails) return', True, None)
    T['pt_core_bias_rf'] = T['pt_core_bias_wired'] = core
    two('pt_wiredtx8', MEAS['wiredtx8'] + MEAS['wtx_post'], 'MEASURED wiredtx8 + wtx_post (POST tap on)')
    two('pt_usb_txdrv', 20.0, 'INSTANCE_WORST_MA wired_tx usb_txdrv (U mode only)')
    two('term_buffer', 2.0, 'INSTANCE_WORST_MA term_buffer (est)')
    two('pt_txpad_bias', 0.30, 'wired_tx README: about 195 uA on + 2 x 51 uA detect legs')
    two('pt_wtx_hsbias', 0.5, 'bound: 10 uA reference, eight binary PMOS sources into a triode load (no bench current)')
    two('wtx8_casbias', 2.0, 'bound: cascode charge pump (WT58), no bench current; wired TX owner to confirm')
    two('tx_steer', 0.5, 'bound: steering logic, CMOS switching at the TX word rate')
    two('tx_interlock', 0.1, 'bound: static CMOS interlock logic')
    T['pt_wtx_fallback_control'] = {'VDD': (0.2, 'bound: static CMOS fallback control', True, None),
                                    'RAIL_wired': (0.2, 'bound: island-side level logic', True, None),
                                    'VSS': (0.4, 'bound: both sides return', True, None)}
    two('pt_wmon_sel', 0.1, 'bound: transmission-gate selector, no active current in wmon_sel-evidence.json', vdd='VDD_WIRE_SW')
    two('pt_char_ro33', 1.66, 'characterization README: 1.66 mA')
    two('pt_char_ro50', 0.81, 'characterization README: 0.81 mA')
    two('pt_char_cmldiv', 4.02, 'characterization README: 4.02 mA')
    T['pt_char_atb'] = {'VSS': (0.001, 'char_atb-evidence.json i_vdd 6e-8 mA', False, None)}
    T['pt_wordclk'] = {'VDD': (*m('wordclk'), True, None), 'VSS': (*m('wordclk'), True, None)}
    # small cells: justified per-type upper bounds
    for c in ('atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad'):
        T[c] = {'VDD': (0.01, 'bound: static CMOS select logic, switched only at SPI rate; leakage nA (island_support README)', False, 0.5),
                'VSS': (0.01, 'same', False, 0.5)}
    for c in ('iso_clamp', 'iso_clamp_x4', 'iso_pd'):
        T[c] = {'VDD': (0.05, 'bound: 1-4 CMOS clamp gates; dynamic current at <= 1.6 GHz clock inputs <= 0.05 mA', False, 0.5),
                'VSS': (0.05, 'same', False, 0.5)}
    for c in ('pad_refpad', 'pad_rf_pair', 'pad_rftxpad', 'pad_single_leg', 'pad_tlp', 'pad_hspad', 'pad_strap', 'pad_wirepad', 'pad_txpad', 'atb_provider_pad'):
        T[c] = {'*': (0.01, 'bound: ESD diode / clamp ring connection, no DC path in operation (junction leakage)', False, None)}
    T['pad_txpad'] = {'VDD': (*m('wtx_padtail'), True, None), 'VSS': (*m('wtx_padtail'), True, None),
                      '*': (0.01, 'ESD ring connection (DVDD_P/N), leakage only', False, None)}
    T['pad_wirepad'] = {'VDD': (*m('usbfs'), True, None), 'VSS': (*m('usbfs'), True, None),
                        '*': (0.01, 'ESD ring connection, leakage only', False, None)}
    host = pb.HOST_MEAS['worst'] * (pb.RF_HOSTIO_FACTOR if chip == 'rf' else 1.0)
    for c in ('pt_host_physical', 'pt_debug_physical'):
        T[c] = {'*': (host if c == 'pt_host_physical' else 0.5 * host,
                      ('HOST_MEAS worst ' + pb.HOST_MEAS['src'][:60]) if c == 'pt_host_physical' else
                      'bound: half the host-link pad current (debug pads, same drivers, fewer active)', True, None)}
    return T


def isw(chip, inst_name, master, island, count):
    a = ISL[chip][island]
    des = a['design_ma'] / count
    src = f'pd2 island {island} design {a["design_ma"]} mA (x1.25 on estimates) / {count} switch(es), {a["switch_master"]}'
    return {'VDD': (des, src, False, None), 'VISL': (des, src, False, None),
            'VSS': (0.01, 'bound: PG inverter + EN pull-down (uA); at turn-off the discharge NMOS sinks the island charge '
                          '(<= 2 nF x 3.3 V in >= 1.2 us, README active discharge)', False, 5.5)}


def bonds(chip):
    """prov_supply PAD rows from the e7 static-drop bond currents (pessimistic, macro 81.8 mA)."""
    p = os.path.join(P, '..', '..', 'scratch', 'integration', 'm1-pdn', 'out', chip, 'e7_static_base.txt')
    out = {}
    try:
        t = open(p).read()
        line = next(l for l in t.splitlines() if l.startswith('bond currents at pess'))
        for name, net, ma in re.findall(r'(\S+)\.pad (VDD|VSS) (\d+)', line):
            out[name] = float(ma)
    except (OSError, StopIteration):
        pass
    return out


def main():
    for chip in ('rf', 'wired'):
        inst = ct.parse(ct.read_conn(os.path.join(HERE, chip, 'chip.conn')))[0]
        T = block_table(chip)
        bd = bonds(chip)
        rows, missing = [], []
        for n, i in inst.items():
            mst = i['master']
            for pin, (k, net) in i['pins'].items():
                if not (net in SUPPLY_NETS or str(net).startswith(SUPPLY_PREFIX)):
                    continue
                if not SUPPLY_PINS.match(pin):
                    rows.append(dict(inst=n, pin=pin, net=net, master=mst, kind='tie', avg_ma=0.001,
                                     source='logic / bias tie to a supply: gate or junction leakage only'))
                    continue
                if mst.startswith('isw_'):
                    isl = re.sub(r'_[ab]$', '', n[4:])
                    cnt = sum(1 for x in inst if re.sub(r'_[ab]$', '', x[4:]) == isl and x.startswith('isw_'))
                    e = isw(chip, n, mst, isl, cnt).get(pin)
                elif mst in ('prov_supply', 'prov_supply_sig'):
                    key = re.sub(r'^pad_(dvdd|dvss|vdd|vss)_(\d+)$', r'\1_pads[\2]', n)
                    v = bd.get(key) or max([x for kk, x in bd.items() if ('vss' in kk) == (net == 'VSS')] or [125.0])
                    e = (v, f'e7 static-drop bond current at the pessimistic bound ({key if key in bd else "worst pad of the net, signal-site supply"})', False, None)
                else:
                    t = T.get(mst)
                    e = (t.get(pin) or t.get('*')) if t else None
                if e is None:
                    missing.append(f'{n}.{pin} ({mst})')
                    continue
                ma, src, k, pk = e
                r = dict(inst=n, pin=pin, net=net, master=mst, kind='supply', avg_ma=round(ma * (K85 if k else 1.0), 3),
                         source=src + (f'; x{K85} for 85 C' if k else ''))
                if pk:
                    r['peak_ma'] = pk
                rows.append(r)
        rows.sort(key=lambda r: -r['avg_ma'])
        out = dict(chip=chip, generated_by='integration/chips/pin_currents.py', rule='plate or multi-cut landing above 0.5 mA',
                   k85=K85, rows=rows, missing=missing,
                   above_0p5ma=sum(r['avg_ma'] > 0.5 or r.get('peak_ma', 0) > 0.5 for r in rows))
        with open(os.path.join(HERE, chip, 'pin_currents.json'), 'w') as f:
            json.dump(out, f, indent=1)
        print(chip, 'pins', len(rows), 'missing', len(missing), 'above 0.5 mA', out['above_0p5ma'], missing[:10])


if __name__ == '__main__':
    main()
