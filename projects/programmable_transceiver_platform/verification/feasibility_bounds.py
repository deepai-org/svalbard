#!/usr/bin/env python3
"""Conditional analytic envelopes, not GF180 performance or foundry guarantees."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; PROJECT=ROOT/'projects/programmable_transceiver_platform'
k=1.380649e-23; T=300.15
lo=[]
for evm_db in (-20,-25,-30,-35):
    e=10**(evm_db/20)
    # Small residual-phase error only, allocating one quarter of EVM power.
    phi=e/2
    lo.append(dict(total_evm_db=evm_db,phase_only_rms_rad=phi,equivalent_time_rms_ps=phi/(2*math.pi*2.4e9)*1e12))
converters=[]
for n in (6,8,10,12):
    q=1/(2**n*math.sqrt(12))
    converters.append(dict(bits=n,full_scale_diff_vpp=1,ideal_full_scale_sine_sqnr_db=6.020599913*n+1.760912591,
        quantization_rms_v=q,diff_sampling_cap_per_leg_pf=(2*k*T/(q/2)**2)*1e12))
jitter=[dict(baseband_input_hz=f,snr_db=s,aperture_jitter_rms_ps=10**(-s/20)/(2*math.pi*f)*1e12) for f in (5e6,10e6) for s in (40,50,60,70)]
noise_dbm=10*math.log10(k*T*20e6/1e-3)
sensitivity=[dict(noise_figure_db=nf,required_snr_db=snr,sensitivity_dbm=noise_dbm+nf+snr) for nf in (5,10,15) for snr in (10,20,30)]
budgets=dict(core=.048,host=.110,wired=.096,rf=.048,pll=.048)
power=3.3*sum(budgets.values())
bounce=[dict(inductance_nh=l,step_ma=i,edge_ps=dt,unmitigated_bounce_v=l*1e-9*i*1e-3/(dt*1e-12)) for l in (.2,1,2) for i in (5,20) for dt in (100,500)]
reservoir=[dict(step_ma=i,interval_ns=dt,droop_mv=20,ideal_cap_pf=i*1e-3*dt*1e-9/.02*1e12) for i in (5,20) for dt in (.1,.5,1)]
r=dict(status='conditional_analytic_scenarios_not_qualification',temperature_k=T,
    lo_residual_phase_scenarios=lo,baseband_aperture_jitter_scenarios=jitter,
    converter_thermal_lower_bounds=converters,thermal_noise_20mhz_dbm=noise_dbm,receiver_sensitivity_scenarios=sensitivity,
    planning_current_a=budgets,sum_planning_current_a=sum(budgets.values()),sum_planning_power_at_3p3_v_w=power,
    thermal_scenarios=[dict(theta_ja_k_per_w=theta,rise_k=theta*power) for theta in (10,30,60,100)],
    supply_inductance_scenarios=bounce,ideal_local_reservoir_scenarios=reservoir,
    assumptions=['EVM values, NF, required SNR, package inductance and thetaJA are exploratory scenarios, not frozen specs or validated bounds.',
      'LO phase allocation uses 25% of total EVM power; equivalent time is not a full phase-noise mask or PLL requirement.',
      'Aperture jitter evaluated at baseband frequency, not the RF carrier; independent sampling and LO error budgets.',
      'Sampling C assumes two independent kT/C legs and thermal RMS <= half quantization RMS. Other circuit noise and settling excluded.',
      '350 mA is a sum of unqualified planning ceilings, not measured current or safe pad/package capacity.',
      'L di/dt omits decoupling/resonance; I dt/C omits ESR/ESL. Neither predicts the actual PDN.',
      'No finite sensitivity sweep proves tolerance of an unknown physical quantity with no justified bound.'],
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
assert abs(power-1.155)<1e-12
assert all(lo[i]['equivalent_time_rms_ps']>lo[i+1]['equivalent_time_rms_ps'] for i in range(len(lo)-1))
assert abs(converters[-1]['diff_sampling_cap_per_leg_pf']/converters[-2]['diff_sampling_cap_per_leg_pf']-16)<1e-10
(PROJECT/'evidence/feasibility-bounds.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(lo=lo,converters=converters,power_w=power,thermal_noise_dbm=noise_dbm),indent=2))
