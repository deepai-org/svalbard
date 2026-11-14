#!/usr/bin/env python3
"""Consolidation pass 4 inventory: every instance of integration/top/pt_chip.conn with class, area, current, modes.
Plain CSV + markdown out. Read-only on design files.  python3 inventory.py"""
import sys, json, re, csv, collections, os
R = '/home/ubuntu/svalbard'
P = f'{R}/projects/programmable_transceiver_platform'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f'{P}/integration/top')
import check_top  # parser only

inst, ports, waive, err = check_top.parse(open(f'{P}/integration/top/pt_chip.conn').read())
assert not err, err[:5]

# ---- areas (um2) --------------------------------------------------------------------------------------------------
util = {k.split(':')[1]: v for k, v in json.load(open(f'{R}/scratch/area-pass-4/util.json')).items()}
ab5 = {k: v['bbox'] for k, v in json.load(open(f'{R}/scratch/chip-assembly-v5/run2/abstracts.json')).items()}
ALIAS = {'tx_steer': 'tx_steering_buffer_flat', 'term_buffer': 'buffer_compensated_flat', 'pad_tlp': 'pad_tlp_flat'}
PAD_DEPTH0 = 442.0   # provider ring band; core intrusion of a custom pad = w x (h - 442)
MANUAL = {  # um2, with the source
    'iso_clamp': (31.28*28.96, 'iso-placement.json size_um'),
    'iso_clamp_x4': (32.88*31.18, 'iso-placement.json size_um'),
    'iso_pd': (9.3*10.21, 'iso-placement.json size_um'),
    'pt_digital_macro': (2.814e6, 'report-v6 digital_mm2'),
    'pt_lna_ind': (220*220, 'RF RX note: 220 um tank coil (est)'),
    'pt_lna_deg': (120*120, 'est: 0.47 nH spiral'),
    'pt_bias_ext': (9000, 'est: 3 bank outputs (bank3 = 4210-8964 um2)'),
    'pt_lo_vreg': (0.5*163000, 'est: half of pll_vreg2 (one regulator, 25 mA)'),
    'pt_refvcm': (3000, 'est'),
    'pt_txpad_bias': (3000, 'est'),
    'pad_strap': (0, 'provider pad site'),
    'pt_host_physical': (0, 'provider pad ring'), 'pt_debug_physical': (0, 'provider pad ring'),
    'atb_provider_pad': (0, 'provider pad ring'),
    'pt_cdr': (259*320, 'r13 published (SESSION-STATE)'),
}

def area(master):
    m = ALIAS.get(master, master)
    if master in MANUAL:
        return MANUAL[master]
    if m.startswith('pad_') and m in util and m != 'pad_tlp_flat':
        b = ab5.get(m)
        w, h = (b[2]-b[0], b[3]-b[1]) if b else (None, None)
        if m == 'pad_hspad': w, h = 478.0, 1111.25
        if m == 'pad_wirepad': w, h = 521.2, 1434.72
        return (w*(h-PAD_DEPTH0), f'core intrusion {w:.0f} x ({h:.0f}-442)')
    if m in util:
        return (util[m]['outline_um2'], 'area-pass-4 util.json outline')
    for k in (m, m.replace('pt_', '')):
        if k in ab5:
            b = ab5[k]; return ((b[2]-b[0])*(b[3]-b[1]), 'v5 abstract bbox')
    if master == 'tx_interlock':
        b = ab5['attached_tx_interlock']; return ((b[2]-b[0])*(b[3]-b[1]), 'v5 abstract bbox')
    if master == 'por':
        b = ab5['por']; return ((b[2]-b[0])*(b[3]-b[1]), 'v5 abstract bbox')
    return (None, 'no area source')

# ---- function class, current (mA nominal / worst, power-delivery.md section 1), modes -------------------------------
# modes: W wired RX/TX (HS pair), U USB, T TMDS TX, E 100BASE-TX, RX/TX/DX radio, a = autonomous LO, dbg = debug only, all
RULES = [  # (instance regex, class, mA nominal, mA worst, modes, PD2 island)
    (r'digital$', 'digital', 72.1, 81.8, 'all', 'core'),
    (r'host$|debug_pads$|atb\d_io$|pad_por_bypass$', 'provider pad', 0, 0, 'all', 'ring'),
    (r'por$', 'bias/ref/monitor', 0.01, 0.01, 'all', 'core'),
    (r'aosc$', 'oscillator', 0.38, 0.48, 'all', 'core'),
    (r'core_bias$', 'bias/ref/monitor', 0.40, 0.52, 'all', 'core'),
    (r'bias_ext$', 'bias/ref/monitor', 0.03, 0.05, 'RXa W U', 'core'),
    (r'isw_', 'island switch', 0, 0, 'all', 'core'),
    (r'pad_rf_rx$', 'pad', 0, 0, 'RX DX', 'rf_rx'), (r'pad_rf_tx$', 'pad', 0, 0, 'TX DX', 'rf_tx'),
    (r'pad_bb_', 'pad (debug)', 0, 0, 'dbg/fallback RX', 'debug'),
    (r'pad_wclk_in$', 'pad (fallback)', 0, 0, 'T(fwd clk) W-fallback', 'debug'),
    (r'pad_wtx_ext$', 'pad (fallback)', 0, 0, 'W-fallback', 'debug'),
    (r'pad_wmon$', 'pad (debug)', 0, 0, 'dbg W U', 'debug'), (r'pad_tlp$', 'test structure', 0, 0, 'char', 'core'),
    (r'pad_ref$', 'pad', 0, 0, 'all (REF or LO_I)', 'pll'), (r'pad_aux_clk$', 'pad', 0, 0, 'RXe/TXe (LO_Q) / aux', 'pll'),
    (r'refvcm$', 'bias/ref/monitor', 0.05, 0.1, 'RX TX', 'pll'),
    (r'pad_hs_rx$', 'pad', 0, 0, 'W E', 'wired_rx'), (r'pad_usb$', 'pad', 18.2, 20.0, 'U', 'wired_tx'),
    (r'pad_wire_tx$', 'pad', 0, 0, 'W T E', 'wired_tx'),
    (r'lna$', 'RF', 18.9, 21.4, 'RX DX', 'rf_rx'), (r'lna_(ind|deg)', 'RF passive', 0, 0, 'RX DX', 'rf_rx'),
    (r'rxmix_', 'RF', 3.01, 3.09, 'RX DX', 'rf_rx'), (r'bbfilter_', 'baseband', 5.22, 5.32, 'RX DX (+TX recon TDD)', 'rf_rx'),
    (r'bb_tap_[iq]$', 'debug tap', 1.0, 1.5, 'dbg/fallback RX', 'debug'), (r'bb_tap_wmon$', 'debug tap', 1.0, 1.5, 'dbg W U', 'debug'),
    (r'iso_', 'isolation', 0, 0, 'all', 'core'),
    (r'adc_', 'converter', 5.73, 6.30, 'RX DX', 'conv'), (r'dac_', 'converter', 2.07, 2.28, 'TX DX', 'conv'),
    (r'refbuf$', 'bias/ref/monitor', 1.56, 1.56, 'RX TX DX', 'conv'),
    (r'txmix_', 'RF', 1.0, 1.0, 'TX DX', 'rf_tx'), (r'txsum$', 'RF', 2.01, 2.03, 'TX DX', 'rf_tx'),
    (r'rfdriver$', 'RF', 58.4, 61.7, 'TX DX', 'rf_tx'),
    (r'lo_ext$', 'LO', 11.3, 13.74, 'RX TX DX', 'lod'), (r'lo_vreg$', 'regulator', 0.5, 1.0, 'RXa TXa DXa', 'lo'),
    (r'qvco$', 'oscillator', 26.5, 29.0, 'RXa TXa DXa', 'lo'), (r'lo_mmd$', 'divider', 26.3, 34.8, 'RXa TXa DXa', 'lod'),
    (r'lo_mmd_qdum$', 'divider (dummy)', 8.0, 10.0, 'RXa TXa DXa', 'lod'),
    (r'lo_pfdcp$', 'PLL', 1.0, 1.5, 'RXa TXa DXa', 'lo'), (r'lo_lf$', 'PLL', 0, 0, 'RXa TXa DXa', 'lo'),
    (r'lo_obs', 'debug tap', 0.5, 1.0, 'dbg RXa', 'lod'), (r'polyphase$', 'test structure', 2.8, 2.8, 'none (tied off, D-POLY)', 'pll'),
    (r'rx_ref_in$', 'clock rx', 3.49, 4.63, 'W U T E RXa', 'core'), (r'clockmux$', 'clock', 1.35, 1.55, 'all', 'pll'),
    (r'prescale', 'divider', 1.99, 2.40, 'all (per instance, see D-CLK)', 'pll'), (r'wordclk$', 'divider', 2.30, 2.42, 'W U E', 'pll'),
    (r'pll_vreg2$', 'regulator', 0.6, 1.0, 'W U T E (+host_follow)', 'pll'),
    (r'pll_tx$', 'oscillator', 6.94, 10.2, 'W U T E', 'pll'), (r'pll_cdr$', 'oscillator', 6.94, 10.2, 'W U E (+host_follow RF)', 'pll'),
    (r'cdr$', 'PLL', 0.4, 1.0, 'W U E', 'pll'),
    (r'rx_aux_clk$', 'clock rx', 3.49, 4.63, 'dbg / aux ref', 'debug'), (r'rx_wclk_in$', 'clock rx', 3.49, 4.63, 'T W-fallback', 'debug'),
    (r'rx_wtx_ext$', 'clock rx', 3.49, 4.63, 'W-fallback', 'debug'),
    (r'ring_osc$', 'oscillator (monitor)', 1.0, 2.0, 'dbg / supply trim readout', 'debug'),
    (r'vco_replica$', 'oscillator (monitor)', 6.0, 11.8, 'dbg', 'debug'),
    (r'obs_pre4', 'divider', 1.0, 1.5, 'dbg', 'debug'), (r'clk_obs$', 'debug mux', 4.96, 4.96, 'dbg', 'debug'),
    (r'pd_clk_obs$', 'isolation', 0, 0, 'dbg', 'core'),
    (r'termination$', 'termination', 1.25, 1.56, 'W U E', 'wired_rx'), (r'rxlevel$', 'bias/ref/monitor', 0.03, 0.04, 'W U E', 'wired_rx'),
    (r'ctle$', 'baseband', 11.2, 12.2, 'W E', 'wired_rx'), (r'rxselect$', 'mux', 2.0, 2.0, 'W U E', 'wired_rx'),
    (r'wmon_sel$', 'debug mux', 0, 0, 'dbg W U', 'wired_rx'), (r'detect$', 'detector', 2.31, 2.38, 'W U', 'wired_rx'),
    (r'vthdac$', 'small DAC', 0.53, 0.70, 'E (W optional)', 'wired_rx'), (r'ptrim$', 'clock trim', 18.0, 21.0, 'W U E', 'wired_cap'),
    (r'slicer$', 'sampler', 7.25, 9.80, 'W U E', 'wired_rx'), (r'wrx_cap$', 'deserializer', 44.78, 46.64, 'W U E', 'wired_cap'),
    (r'wiredtx$', 'serializer', 35.3, 37.46, 'W T E', 'wired_tx'), (r'steer_', 'pad driver', 0, 0, 'W T E (4,5 unused)', 'wired_tx'),
    (r'attached_tx_interlock$', 'control', 0, 0, 'W T E U', 'wired_tx'), (r'term_buffer$', 'termination', 1.0, 1.5, 'W T E', 'wired_tx'),
    (r'txpad_bias$', 'bias/ref/monitor', 0.1, 0.2, 'W T E', 'wired_tx'), (r'hsbias$', 'bias/ref/monitor', 0.3, 0.5, 'U', 'wired_tx'),
    (r'wtx_fallback_control$', 'control', 0, 0, 'W-fallback', 'wired_tx'),
    (r'atb\d_leaf', 'ATB', 0, 0, 'dbg', 'core'), (r'atb\d_grp', 'ATB', 0, 0, 'dbg', 'core'), (r'atb\d_pad', 'ATB', 0, 0, 'dbg', 'core'),
]

rows = []
for name, d in inst.items():
    for rx, cls, inom, iw, modes, isl in RULES:
        if re.match(rx, name):
            break
    else:
        cls, inom, iw, modes, isl = '?', 0, 0, '?', '?'
    a, src = area(d['master'])
    npin = len(d['pins'])
    nctl = sum(1 for k, (kind, net) in d['pins'].items() if net.startswith('c_'))
    tied = sum(1 for k, (kind, net) in d['pins'].items() if net in ('VSS', '-') and kind in '=>')
    rows.append(dict(inst=name, master=d['master'], conn_group=d['group'], demand='demand' in d['flags'], cls=cls,
                     area_um2=None if a is None else round(a), area_src=src, mA_nom=inom, mA_worst=iw, modes=modes,
                     pd2_island=isl, pins=npin, ctl_pins=nctl, tied_or_nc=tied))

with open(f'{HERE}/inventory.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---- markdown summaries -------------------------------------------------------------------------------------------
bym = collections.OrderedDict()
for r in rows:
    k = r['master']
    e = bym.setdefault(k, dict(n=0, a=r['area_um2'], cls=r['cls'], insts=[], mA=0.0, modes=set(), src=r['area_src'], ctl=0))
    e['n'] += 1; e['insts'].append(r['inst']); e['mA'] += r['mA_nom']; e['modes'].add(r['modes']); e['ctl'] += r['ctl_pins']
out = ['# Inventory by master (generated by inventory.py from pt_chip.conn)', '',
       f'{len(rows)} instances, {len(bym)} masters. Area = outline (pads: core intrusion). mA = nominal, sum over instances.', '',
       '| master | class | n | um2 each | mm2 total | mA total | ctl pins | modes | area source |', '|---|---|---:|---:|---:|---:|---:|---|---|']
tot = 0
for k, e in sorted(bym.items(), key=lambda kv: -((kv[1]['a'] or 0)*kv[1]['n'])):
    t = (e['a'] or 0)*e['n']/1e6; tot += t
    out.append(f"| {k} | {e['cls']} | {e['n']} | {e['a'] if e['a'] is not None else '?'} | {t:.4f} | {e['mA']:.2f} | {e['ctl']} | {'; '.join(sorted(e['modes']))} | {e['src']} |")
out += ['', f'Total (digital macro and pad intrusion included): {tot:.3f} mm2', '']
byc = collections.defaultdict(lambda: [0, 0.0, 0.0])
for r in rows:
    c = byc[r['cls']]; c[0] += 1; c[1] += (r['area_um2'] or 0)/1e6; c[2] += r['mA_nom']
out += ['## By function class', '', '| class | instances | mm2 | mA nominal (all on, not a mode) |', '|---|---:|---:|---:|']
for k, c in sorted(byc.items(), key=lambda kv: -kv[1][1]):
    out.append(f'| {k} | {c[0]} | {c[1]:.3f} | {c[2]:.1f} |')
# duplicates: masters with n > 1
out += ['', '## Masters instanced more than once (mechanical duplicate list)', '', '| master | n | mm2 total | instances |', '|---|---:|---:|---|']
for k, e in sorted(bym.items(), key=lambda kv: -((kv[1]['a'] or 0)*kv[1]['n'])):
    if e['n'] > 1:
        names = e['insts'] if e['n'] <= 8 else e['insts'][:4] + ['...'] + e['insts'][-2:]
        out.append(f"| {k} | {e['n']} | {(e['a'] or 0)*e['n']/1e6:.4f} | {' '.join(names)} |")
# pins tied off / unused outputs per instance: partially used hardware
out += ['', '## Instances with tied-off inputs or no-connect outputs (partially used hardware)', '',
        '| inst | master | pins | tied to VSS or open | which |', '|---|---|---:|---:|---|']
for name, d in inst.items():
    if re.match(r'atb|iso_', name): continue
    t = [f'{k}{kind}{net}' for k, (kind, net) in d['pins'].items() if net in ('VSS', '-') and not re.fullmatch(r'VSS|GND|AGND|VSUB|vss', k)]
    if len(t) >= 2:
        out.append(f"| {name} | {d['master']} | {len(d['pins'])} | {len(t)} | {' '.join(t)[:260]} |")
open(f'{HERE}/inventory.md', 'w').write('\n'.join(out)+'\n')
print('\n'.join(out))
