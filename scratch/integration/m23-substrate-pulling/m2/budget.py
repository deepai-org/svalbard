#!/usr/bin/env python3
"""M2 budget on the v6 outline floorplan: aggressor bounce (opt/nom/pess) x mesh transfer x victim rejection vs criterion.
Aggressor amplitudes: M1 (scratch/reviews/integration-m1.md, e3 bounce: macro 80/240/418 mV pk-pk VDD-VSS with the AP4-9 decap,
150/620/2070 with the 0 nF that v6 actually places; half of it taken on the VSS/substrate side, amplitude = pp/4), A2/A3, block READMEs.
Transfer: opt = dense ties + grounded backside (victim tied), nom = dense ties + floating backside (victim tied),
pess = sparse ties + floating backside + 3x surface skin (victim tied); 'float' = same as pess but the victim's own taps do not
hold its substrate (floating probe: the bound if the victim ground is not the reference of its sensitive node).
Victim rejection (substrate/ground bounce -> error at the sensitive node) is ASSUMED two-sided, not extracted (see report)."""
import json, numpy as np
d = json.load(open('v6_matrix_h50.json'))
T = lambda a, v, c, k='tied_near_db': 10**(d[c][a][v][k]/20)
def tr(a, v): return (T(a, v, 'dense_backgnd'), T(a, v, 'dense_float'), T(a, v, 'sparse_float_skin3'), T(a, v, 'sparse_float_skin3', 'near_db'))
LSB = 1.56e-3
# aggressor: (opt, nom, pess) local substrate/ground bounce amplitude in V pk, and the note
AGG = {
 'digital@78MHz (planned decap)': ('digital', (0.020, 0.060, 0.105)),
 'digital@78MHz (v6 as placed, 0 nF)': ('digital', (0.037, 0.155, 0.52)),
 'digital in-band <10MHz (2/5/15 % of the 78 MHz bounce)': ('digital', (0.0004, 0.003, 0.016)),
 'digital@2421.875MHz (M1 die-VSS line, pk)': ('digital', (0.00048, 0.0042, 0.0208)),
 'pll_cdr ring (host-follow, RF mode)': ('pll_cdr', (0.002, 0.005, 0.020)),
 'wired front end (wired mode)': ('wired_fe(ctle+detect+term)', (0.010, 0.030, 0.100)),
 'rfdriver ground @f0/2f0': ('rfdriver', (0.0005, 0.003, 0.020)),
 'pad_rf_tx capacitive @f0 (effective monopole)': ('pad_rf_tx', (0.002, 0.008, 0.030)),
 'lo_mmd @f_LO': ('lo_mmd', (0.002, 0.005, 0.020)),
}
# victim criteria: (rejection dB opt/nom/pess, allowed error V, post-gain, text)
def row(an, vn, rej, allowed, gain=1.0, what=''):
    key, amp = AGG[an]; t = tr(key, vn)
    v = [amp[i]*t[i] for i in range(3)]+[amp[2]*t[3]]
    e = [v[i]*10**(-rej[min(i, 2)]/20)*gain for i in range(4)]
    m = [20*np.log10(allowed/x) for x in e]
    return dict(aggressor=an, victim=vn, what=what, local_bounce_mV=[round(x*1e3, 4) for x in v], error_mV=[round(x*1e3, 5) for x in e],
                allowed_mV=allowed*1e3, margin_dB=[round(x, 1) for x in m], verdict='PASS' if m[2] >= 0 else ('PASS nominal, FAIL pessimistic' if m[1] >= 0 else 'FAIL'))
R = []
for dg in ('digital@78MHz (planned decap)', 'digital@78MHz (v6 as placed, 0 nF)'):
    for v in ('adc_i', 'adc_q'): R.append(row(dg, v, (40, 30, 20), 0.25*LSB, what='0.25 LSB at the ADC (aliases to 1.875 MHz when the converter clock is not host-derived)'))
    R.append(row(dg, 'core_bias', (30, 25, 20), 1e-3, what='<= 1 mV ripple on VBG'))
    R.append(row(dg, 'dac_i', (40, 30, 20), 0.35*10**(-40/20), what='TX spur at +-78 MHz <= -40 dBr of 0.35 V FS (tx_dac_direct: no filter)'))
    R.append(row(dg, 'dac_q', (40, 30, 20), 0.35*10**(-40/20), what='same'))
for v in ('bbfilter_i', 'bbfilter_q'):
    R.append(row('digital in-band <10MHz (2/5/15 % of the 78 MHz bounce)', v, (40, 35, 30), 0.25*LSB, gain=10**(42/20), what='0.25 LSB at the ADC at PGA 42 dB'))
    R.append(row('digital in-band <10MHz (2/5/15 % of the 78 MHz bounce)', v, (40, 35, 30), 0.25*LSB, gain=10**(24/20), what='0.25 LSB at the ADC at PGA 24 dB'))
R.append(row('digital@2421.875MHz (M1 die-VSS line, pk)', 'lna', (38, 35, 33), 2.24e-6*1.414, what='<= -100 dBm in-band spur (pad divider 8 dB + CMRR 30/27/25)'))
R.append(row('digital@2421.875MHz (M1 die-VSS line, pk)', 'pad_rf_rx', (38, 35, 33), 2.24e-6*1.414, what='same, at the RF_RX pad cell'))
for v in ('adc_i', 'adc_q'): R.append(row('pll_cdr ring (host-follow, RF mode)', v, (40, 30, 20), 0.25*LSB, what='0.25 LSB (625 MHz aliases; 16th harmonic of fs when host-derived -> DC)'))
R.append(row('wired front end (wired mode)', 'adc_q', (40, 30, 20), 0.25*LSB, what='0.25 LSB, only if the ADC runs in a wired mode'))
R.append(row('wired front end (wired mode)', 'core_bias', (30, 25, 20), 1e-3, what='<= 1 mV on VBG'))
R.append(row('lo_mmd @f_LO', 'lna', (38, 35, 33), 0.447e-3, what='LO at RF_RX <= -57 dBm (0.447 mV pk)'))
R.append(row('lo_mmd @f_LO', 'core_bias', (30, 25, 20), 1e-3, what='<= 1 mV on VBG (2.4 GHz: far above the bandgap bandwidth)'))
R.append(row('rfdriver ground @f0/2f0', 'lna', (38, 35, 33), 0.030, what='TX->RX isolation >= 30 dB (GX-9): <= 30 mV pk at the LNA input at +9.5 dBm'))
R.append(row('pad_rf_tx capacitive @f0 (effective monopole)', 'lna', (38, 35, 33), 0.030, what='same'))
R.append(row('rfdriver ground @f0/2f0', 'adc_i', (40, 30, 20), 0.25*LSB, what='0.25 LSB'))
R.append(row('rfdriver ground @f0/2f0', 'core_bias', (30, 25, 20), 1e-3, what='<= 1 mV on VBG'))
R.append(row('rfdriver ground @f0/2f0', 'dac_i', (40, 30, 20), 0.35*10**(-40/20), what='<= -40 dBr'))
# D2H route: current injection
RHO = (0.05, 0.10, 0.30); IINJ = (1.5e-3, 5e-3, 13e-3); H = 50e-6
for rn in [k for k in d['sparse_float'] if k.startswith('d2h')]:
    for v in ('adc_i', 'adc_q', 'bbfilter_i', 'pll_cdr'):
        z = [d[c][rn][v]['near_ohm_norm'] for c in ('dense_backgnd', 'dense_float', 'sparse_float_skin3')]
        vb = [IINJ[i]*z[i]*RHO[i]/H for i in range(3)]
        rej = (40, 30, 20); e = [vb[i]*10**(-rej[i]/20) for i in range(3)]; m = [20*np.log10(0.25*LSB/x) for x in e]
        R.append(dict(aggressor=rn+' (unshielded lanes, C to substrate 0.9-2.4 pF, 3.3 V, 0.3-1 ns)', victim=v, what='0.25 LSB (floating-probe transimpedance; rho 5/10/30 ohm cm)',
                      local_bounce_mV=[round(x*1e3, 3) for x in vb], error_mV=[round(x*1e3, 4) for x in e], allowed_mV=0.25*LSB*1e3, margin_dB=[round(x, 1) for x in m],
                      verdict='PASS' if m[2] >= 0 else ('PASS nominal, FAIL pessimistic' if m[1] >= 0 else 'FAIL')))
json.dump(R, open('budget_v6.json', 'w'), indent=1)
for r in R: print(f"{r['aggressor'][:44]:44s} -> {r['victim']:10s} bounce {r['local_bounce_mV']} mV | margin {r['margin_dB']} dB | {r['verdict']}")
