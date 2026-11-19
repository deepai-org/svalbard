"""Aggressor spectra of the chip PDN model (DC loads per case come from chipcfg.dc_loads). Every number cites its evidence."""
import sys, json, numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/spec/budgets')
import power_budget as pb          # read-only (MEASURED, dig_meas, switch masters); main() is not called
MAP = {}     # budget block -> (floorplan tap, island or None = raw ring); filled per chip by chipcfg.apply

def dc_loads(case, level):
    import chipcfg
    return chipcfg.dc_loads(case, level)

WTX_MA = (53.0, 84.0, 105.0)   # opt / nom / pess wired_tx island current (set by chipcfg.apply)

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
        i = pk(WTX_MA[2], WTX_MA[1], WTX_MA[0])*1e-3   # pt_wiredtx8 + POST + pad tail (chipcfg.WTX_MA from power_budget MEASURED)
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
