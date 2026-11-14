#!/usr/bin/env python3
"""M3b/c budgets: PA -> QVCO injection pulling (Adler), LO -> LNA leakage, ext-LO bond coupling.
Inputs: mutual.json (Neumann M, two-sided), qvco/qvco_sens.json (extracted QVCO r6b injection sensitivities), M2 mesh numbers.
Frequency plan (established from analog/timing/README.md + analog/rf_tx/README.md): the QVCO runs AT the RF carrier (2.30-2.70 GHz
tuning range, quadrature LC, no divider between tank and mixers; lo_mmd is only the PLL feedback divider), the TX is direct
conversion and the on-chip rfdriver delivers up to +9.5 dBm at the same frequency.  LO-01 ("never run the VCO at f_RF") is closed
in the risk register but the as-built QVCO violates it.

Pulling model.  Injection equivalent to a series EMF e in the tank inductor: one-sided lock range f_L = f0 e /(2 V_tank)
(Adler with I_inj = e/(wL), I_osc = V/(Q w L): Q cancels).  The PA output is the LO times the complex modulation m(t), so the
injection is co-frequency and modulated: the VCO phase obeys d(theta)/dt = 2 pi f_L(t) sin(phi_inj - theta) - (PLL correction).
Above the PLL bandwidth f_c (300 kHz) the VCO integrates: theta_rms = df_rms / sqrt(B f_c) for a flat quadrature-component
spectrum over 0..B (B = 10 MHz for HE20), df_rms = f_L,pk * m_rms / sqrt(2), m_rms = 10^(-PAPR_backoff/20).
EVM contribution = theta_rms (rad).  Budget: -35 dB (7 dB under the -27.9 dB MCS7 EVM actually measured, so the sum stays
within 1 dB); constant-envelope modes (BLE/15.4 at Psat): static phase offset only (no EVM), criterion = stay locked to the PLL:
f_L < 0.5 * f_c * (K hold-in) is not a constraint for static offset; so OFDM is the binding case."""
import json, numpy as np, os
F0 = 2.45e9; W = 2*np.pi*F0
sens = json.load(open('qvco/qvco_sens.json')) if os.path.exists('qvco/qvco_sens.json') else {}
VT = sens.get('q_base', {}).get('amp_diff_pk_V', 1.42)
L_TANK = 2.2517e-9
KSIM = sens.get('q_dinj', {}).get('ratio_sim_to_adler', 1.0)   # extracted QVCO r6b: simulated f_L / Adler prediction (0.71: the quadrature coupling stiffens the core)
def fL_emf(e): return KSIM*F0*e/(2*VT)
def evm_db(fl_pk, backoff_db=8.0, B=10e6, fc=300e3):
    df = fl_pk*10**(-backoff_db/20)/np.sqrt(2); th = df/np.sqrt(B*fc); return 20*np.log10(max(th, 1e-12)), th
mu = json.load(open('mutual.json'))
I_PA = dict(lo=4e-3, nom=12e-3, hi=35e-3)     # RF current in each RF_TX bond: real load current only (lo) .. plus the pad-C circulating current (hi: 1.4 V pk * w * 1.6 pF)
out = dict(V_tank_diff_pk=VT, I_PA_bond_A=I_PA, pa_to_qvco_bond=[], notes=[])
print('PA bond pair -> QVCO spiral (magnetic).  f_L,pk (kHz) and OFDM EVM contribution (dB), lo/nom/hi; budget -35 dB')
for r in mu['bond_to_spiral']:
    row = dict(dx_um=r['dx_um'], dy_um=r['dy_um'])
    for k in ('lo', 'nom', 'hi'):
        # hi M: envelope (max over the no-image value and the nominal), the no-image case is not monotonic
        M = max(r['M_pH']['hi'], r['M_pH']['nom']) if k == 'hi' else r['M_pH'][k]
        e = W*M*1e-12*I_PA[k]*np.sqrt(2)      # two spirals (I and Q cores) at 90 deg: rss-equivalent upper bound x sqrt(2)
        fl = fL_emf(e); row[k] = dict(M_pH=M, emf_uV=e*1e6, fL_kHz=fl/1e3, evm_dB=evm_db(fl)[0])
    out['pa_to_qvco_bond'].append(row)
    print(f"  dx {r['dx_um']:5d} dy {r['dy_um']:5d} | fL " + ' / '.join(f"{row[k]['fL_kHz']:8.2f}" for k in ('lo', 'nom', 'hi')) + ' | EVM ' + ' / '.join(f"{row[k]['evm_dB']:6.1f}" for k in ('lo', 'nom', 'hi')))
# required: EVM <= -35 dB -> fL_pk
th = 10**(-35/20); fl_req = th*np.sqrt(10e6*300e3)*np.sqrt(2)*10**(8/20)
out['fL_pk_budget_kHz_for_m35dB'] = fl_req/1e3; out['emf_budget_uV'] = fl_req*2*VT/F0/KSIM*1e6; out['sim_to_adler'] = KSIM
print(f"budget: f_L,pk <= {fl_req/1e3:.0f} kHz  <=> series EMF <= {fl_req*2*VT/F0/KSIM*1e6:.0f} uV pk  <=> injection ratio {20*np.log10(fl_req*2/F0/KSIM):.1f} dB re tank swing (sim/Adler {KSIM:.2f})")
# --- supply / substrate paths from the extracted-QVCO sensitivities
if 'q_vddhf' in sens or 'q_subhf' in sens or 'q_dinj' in sens:
    print('extracted QVCO sensitivities:', {k: {a: round(b, 3) for a, b in v.items() if isinstance(b, float)} for k, v in sens.items()})
    budget = fl_req/1e3
    for key, lab in (('q_vddhf', 'VDD tone at f0'), ('q_vdd2f', 'VDD tone at 2 f0'), ('q_subhf', 'substrate tone at f0'), ('q_sub2f', 'substrate tone at 2 f0')):
        if key in sens:
            k = sens[key]['fL_kHz_per_mV']; out[f'allowed_{key}_mV_pk'] = budget/k
            print(f"  {lab:24s}: {k:8.2f} kHz/mV  -> allowed {budget/k*1e3:8.1f} uV pk at the QVCO for the -35 dB EVM budget")
# --- LO -> LNA leakage (magnetic), autonomous and external LO
I_TANK = VT/(W*L_TANK)                                    # circulating tank current (A pk)
I_LOPAD = dict(lo=1.0*W*1.0e-12, nom=1.0*W*1.5e-12, hi=1.0*W*2.0e-12)   # ext LO: 1 V pk per leg into pad C 1.0..2.0 pF
def dbm_from_emf(e_pk, R=50.0): return 10*np.log10((e_pk/np.sqrt(2))**2/(4*R)/1e-3)
GCONV = 10**(22.3/20)                                     # RF pad -> baseband conversion gain with LNA (rf_rx README)
print(f'LO -> RF_RX leakage. tank current {I_TANK*1e3:.1f} mA pk. spec RF-RX-LOLEAK <= -57 dBm; coarse DC trim +-250 mV at the filter input')
out['lo_leak'] = []
for r in mu['bond_to_spiral']:
    if r['dx_um'] not in (1300, 1700): continue
    row = dict(mode='autonomous', dx_um=r['dx_um'], dy_um=r['dy_um'])
    for k in ('lo', 'nom', 'hi'):
        M = max(r['M_pH']['hi'], r['M_pH']['nom']) if k == 'hi' else r['M_pH'][k]
        e = W*M*1e-12*I_TANK*np.sqrt(2); row[k] = dict(dBm=dbm_from_emf(e), dc_mV=e/2*GCONV*1e3)
    out['lo_leak'].append(row)
    print(f"  QVCO at dx {r['dx_um']} dy {r['dy_um']:5d} from RF_RX | " + ' / '.join(f"{row[k]['dBm']:6.1f} dBm" for k in ('lo', 'nom', 'hi')) + ' | DC ' + ' / '.join(f"{row[k]['dc_mV']:6.2f} mV" for k in ('lo', 'nom', 'hi')))
for r in mu['pair_to_pair']:
    row = dict(mode='external LO pair -> RF_RX pair', dy_die_um=r['dy_die_um'])
    for k in ('lo', 'nom', 'hi'):
        e = W*r['M_pH'][k]*1e-12*I_LOPAD[k]; row[k] = dict(dBm=dbm_from_emf(e), dc_mV=e/2*GCONV*1e3)
    out['lo_leak'].append(row)
    print(f"  ext-LO pair at {r['dy_die_um']:5d} um from RF_RX   | " + ' / '.join(f"{row[k]['dBm']:6.1f} dBm" for k in ('lo', 'nom', 'hi')) + ' | DC ' + ' / '.join(f"{row[k]['dc_mV']:6.1f} mV" for k in ('lo', 'nom', 'hi')))
# --- PA pair -> ext-LO pair (TX modulates its own LO in external-LO mode)
print('PA pair -> external-LO pair (AUX_CLK = Q): EMF vs LO 2 V pk diff; peak LO phase error (rad) and OFDM EVM (8 dB backoff)')
out['pa_to_extlo'] = []
for r in mu['pair_to_pair']:
    row = dict(dy_die_um=r['dy_die_um'])
    for k in ('lo', 'nom', 'hi'):
        e = W*r['M_pH'][k]*1e-12*I_PA[k]; ph = e/2.0; row[k] = dict(emf_mV=e*1e3, phase_pk_rad=ph, evm_dB=20*np.log10(ph*10**(-8/20)/np.sqrt(2)))
    out['pa_to_extlo'].append(row)
    print(f"  {r['dy_die_um']:5d} um | " + ' / '.join(f"{row[k]['emf_mV']:7.3f} mV" for k in ('lo', 'nom', 'hi')) + ' | EVM ' + ' / '.join(f"{row[k]['evm_dB']:6.1f}" for k in ('lo', 'nom', 'hi')))
json.dump(out, open('pulling.json', 'w'), indent=1)
