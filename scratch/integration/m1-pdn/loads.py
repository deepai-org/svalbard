"""Block currents (DC per mode) and aggressor spectra for the M1 PDN model. Every number cites its evidence."""
import sys, json, numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/spec/budgets')
import power_budget as pb          # read-only use of mode_totals / apply_rf_recipe (main() is not called)
import model as M
AA = json.load(open(pb.AA))
CASES = {'rf_external_clock': ('external_rf_clock', 'rf_rx'), 'rf_autonomous': (None, 'rf_rx'),
         'wired_onchip_pll': (None, 'wired'), 'wired_external_clock': ('external_wired_clock', 'wired'),
         'wired_tmds': ('wired_tmds', 'wired'), 'usb': (None, 'usb'), 'stopped': (None, 'stopped'),
         'rf_tx_external_clock': ('external_rf_clock', 'rf_tx'), 'rf_tx_autonomous': (None, 'rf_tx'),
         'rf_duplex_external_clock': ('external_rf_clock', 'rf_rx')}
# budget block -> (floorplan tap, island or None = raw ring)
MAP = dict(adc_i=('adc_i', 'conv'), adc_q=('adc_q', 'conv'), aosc=('aosc', None), bias=('core_bias', None),
           cdr=('pll_cdr', 'pll'), clockmux=('clockmux', 'pll'), clocktree=('wordclk', 'pll'), ctle=('ctle', 'wired'),
           dac_i=('dac_i', 'conv'), dac_q=('dac_q', 'conv'), detect=('detect', 'wired'), lna=('lna', 'rf'),
           monitor=('core_bias', None), quadrature=('qvco', 'pll'), refbuf=('refbuf', 'conv'), refinput=('pad_ref', 'pll'),
           rfdriver=('rfdriver', 'rf'), rfpll=('lo_mmd', 'pll'), rxfilter_i=('bbfilter_i', 'rf'), rxfilter_q=('bbfilter_q', 'rf'),
           rxmix_i=('rxmix_i', 'rf'), rxmix_q=('rxmix_q', 'rf'), rxselect=('rxselect', 'wired'), slicer=('slicer', 'wired'),
           termination=('termination', 'wired'), txmix_i=('txmix_i', 'rf'), txmix_q=('txmix_q', 'rf'),
           txpad=('pad_wire_tx', 'wired'), txsum=('txsum', 'rf'), usbdrive=('pad_usb', 'wired'), usbfs=('pad_usb', None),
           usbhs=('pad_usb', 'wired'), wiredtx=('wiredtx', 'wired'), wirepad=('pad_hs_rx', 'wired'), rxlevel=('rxlevel', 'wired'))

def dc_loads(case, level):
    """level: 'alloc' (analog-architecture allocations + RF recipe), 'evid' (power_budget evidence bound: digital 81.79 mA
    vectorless, hostio 116.82 mA 8 pF, rfdriver 61.7 mA), 'evid+' (evid plus currents that exist in block evidence but in
    no budget: wrx_cap 46.64 mA extracted (wrx_cap-evidence ext_q625), LO chain qvco 25 + lo_mmd 34 + lo_ext 16 +
    polyphase 2.8 mA in place of rfpll 12 + quadrature 18.83 (timing README, lo_ext/polyphase evidence))."""
    branch, m = CASES[case]
    per = pb.mode_totals(AA, branch)[m]
    rdir = pb.rf_direction(case, m)
    if rdir: per = pb.apply_rf_recipe(per, rdir)
    per = dict(per)
    if rdir in ('rf_tx', 'rf_duplex'): per['rfdriver'] = 61.7
    if level != 'alloc' and m != 'stopped':
        per['digital'] = 81.79
        per['hostio'] = 116.82*(0.5 if rdir else 1.0)
    out = []   # (name, tap, island, mA)
    for b, ma in per.items():
        if ma <= 0 or b in ('digital', 'hostio'): continue
        if b not in MAP: continue
        t, isl = MAP[b]; out.append((b, t, isl, ma))
    if level == 'evid+':
        if m == 'wired': out.append(('wrx_cap', 'wrx_cap', 'wired', 46.64))
        if case in ('rf_autonomous', 'rf_tx_autonomous'):
            out = [o for o in out if o[0] not in ('rfpll', 'quadrature')]
            out += [('qvco', 'qvco', 'pll', 25.0), ('lo_mmd', 'lo_mmd', 'pll', 34.0), ('lo_ext', 'lo_ext', 'pll', 16.0),
                    ('polyphase', 'polyphase', 'pll', 2.8)]
    return out, per.get('digital', 0.0), per.get('hostio', 0.0), m, rdir

def env(x):
    """Upper envelope of the triangular-pulse spectrum sinc^2(x): 1 below the corner, 1/(pi x)^2 above."""
    return np.minimum(1.0, 1.0/np.maximum(1e-9, np.pi*x)**2)

def lines(case, per_dig, per_host, m, rdir, bound):
    """Aggressor spectral lines: list of (aggressor, port, f_Hz, I_peak_A exact pulse spectrum, I_peak_A envelope without
    the sinc nulls: used only for the in-band RF spur estimate). bound: 'pess' | 'nom' | 'opt'. Pulses are centred at t = 0.
    Ports: dig, d2h0/d2h1 (VDD->board/VSS composite, even/odd harmonic), wrx, wtx, adc, rfd, lo."""
    B = {'pess': 0, 'nom': 1, 'opt': 2}[bound]; pk = lambda *v: v[B]; L = []
    if m == 'stopped': return L
    rf = m.startswith('rf')
    # digital macro: charge packets at 78.125 MHz (hcore). pess: vectorless 81.79 mA (digital-hardening-evidence), 1.6 ns
    # triangle (the A2 pulse shape); nom: the PWR-DIG requirement (60 mA wired/USB, 40 mA RF), 2.4 ns; opt: 24.5 mA
    # clock-pin floor (clock-power-screen), 3 ns.
    i = pk(per_dig, min(per_dig, 40.0 if rf else 60.0), min(per_dig, 24.5))*1e-3; f0 = 78.125e6
    for n in range(1, 41):
        x = n*f0*pk(0.8e-9, 1.2e-9, 1.5e-9)
        L.append(('digital', 'dig', n*f0, 2*i*np.sinc(x)**2, 2*i*env(x)))
    # D2H: 11 pins at 156.25 MHz (78.125 in RF modes: div2 recipe). pess: all alternating in phase, fast edge 0.76 ns;
    # nom: half the periodic content, 1.0 ns; opt: PRBS payload (only D2H_CLK periodic: 0.2x), slow edge 1.4 ns, 5 pF load.
    f0 = 78.125e6 if rdir else 156.25e6
    i = per_host*1e-3*pk(1.0, 0.5, 0.2*95.24/116.82)
    for n in range(1, 21 if not rdir else 41):
        x = n*f0*pk(0.76e-9, 1.0e-9, 1.4e-9)
        L.append(('d2h', 'd2h%d' % (n % 2), n*f0, 2*i*np.sinc(x)**2, 2*i*env(x)))
    if m == 'wired':
        # wrx_cap: 46.64 mA extracted / 19.78 schematic (wrx_cap-evidence ext_q625 / sch_q625) at the ring rate, 4 phases.
        # Content at f_ring, 2f, 4f as a fraction of I_avg: pess 1.0/0.5/0.5 (one-phase-equivalent), nom 0.5/0.25/0.25,
        # opt 0.2/0.1/0.1 (phase-balanced).
        i = pk(46.64, 46.64, 19.78)*1e-3
        for k, fr in ((1, pk(1.0, 0.5, 0.2)), (2, pk(0.5, 0.25, 0.1)), (4, pk(0.5, 0.25, 0.1))):
            L.append(('wrx_cap', 'wrx', k*625e6, fr*i))
        i = pk(37.5, 35.0, 33.2)*1e-3      # pt_wiredtx switching CMOS serializer (scratch/wired_tx/sim-results.json)
        for k, fr in ((1, pk(0.5, 0.25, 0.1)), (2, pk(0.5, 0.25, 0.1)), (4, pk(0.3, 0.15, 0.05))):
            L.append(('wiredtx', 'wtx', k*625e6, fr*i))
    if m == 'rf_rx':
        # SAR ADCs: 5.73 mA each at 40 MS/s, both in phase; conversion-burst pulse base 1 / 2 / 4 ns
        i = 2*5.73e-3
        for n in range(1, 26):
            x = n*40e6*pk(0.5e-9, 1e-9, 2e-9)
            L.append(('adc', 'adc', n*40e6, 2*i*np.sinc(x)**2, 2*i*env(x)))
    if rdir in ('rf_tx', 'rf_duplex'):
        idc = 61.7e-3
        # envelope (20 MHz-wide modulation): supply-current variation 30 / 15 / 5 % of Idc at each of 1/5/10/20 MHz
        for fm in (1e6, 5e6, 10e6, 20e6):
            L.append(('rfdrv_env', 'rfd', fm, pk(0.3, 0.15, 0.05)*idc))
        # RF: fundamental differential imbalance 10 / 5 / 2 % of 2*Idc; 2nd harmonic common-mode 0.4 / 0.2 / 0.1 of Idc
        L.append(('rfdrv_rf', 'rfd', 2.4e9, pk(0.10, 0.05, 0.02)*2*idc))
        L.append(('rfdrv_rf', 'rfd', 4.8e9, pk(0.4, 0.2, 0.1)*idc))
    if rf:
        # LO chain on the pll island: lo_mmd 19-34 mA at ~3 GHz, lo_ext 11.8-16 mA at 2.4 GHz: ripple 30 / 10 / 3 %
        L.append(('lo', 'lo', 3.0e9, pk(0.3*34, 0.1*27, 0.03*19)*1e-3))
        L.append(('lo', 'lo', 2.4e9, pk(0.3*16, 0.1*14, 0.03*11.8)*1e-3))
    return [l if len(l) == 5 else (*l, l[3]) for l in L]
