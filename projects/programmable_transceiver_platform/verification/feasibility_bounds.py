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
# Explicit illustrative reference planes: real RF v(t)=Re{z*exp(jwt)},
# P=E|z|^2/(2R); differential I/Q branch voltage=.5*normalized sample.
# This is an interpretation scenario, not calibrated live-chain port scaling.
reference_planes=[]
for nf in (5.,10.,15.):
    frontend_evm=.04;resistance=50.;complex_signal_v=.2*.5
    input_noise_w=k*T*20e6*10**(nf/10)
    input_signal_w=input_noise_w/frontend_evm**2
    conversion_gain=complex_signal_v/math.sqrt(2*resistance*input_signal_w)
    assert math.isclose(conversion_gain*math.sqrt(2*resistance*input_noise_w)/complex_signal_v,
                        frontend_evm,rel_tol=1e-12)
    reference_planes.append(dict(noise_figure_db=nf,noise_bandwidth_hz=20e6,
        frontend_noise_evm_rms=frontend_evm,rf_resistance_ohm=resistance,
        normalized_complex_signal_rms=.2,differential_volts_per_normalized_unit=.5,
        filter_output_complex_signal_rms_v=complex_signal_v,
        required_rf_input_dbm=10*math.log10(input_signal_w/1e-3),
        required_conversion_voltage_gain_db=20*math.log10(conversion_gain)))
noise_gain=[]
converter_complex_noise=math.sqrt(2*max(0.,2**(2*(1-9))-2**(2*(1-12)))/12)
for gain in (.5,1.,2.):
    frontend=.04;converter=converter_complex_noise/(.2*gain)
    noise_gain.append(dict(rx_gain=gain,frontend_evm_rms=frontend,
        converter_excess_noise_evm_rms=converter,combined_evm_rms=math.hypot(frontend,converter),
        legacy_post_gain_combined_evm_rms=math.hypot(.2*frontend,converter_complex_noise)/(.2*gain)))
contract=json.loads((PROJECT/'spec/contract.json').read_text())
budgets={('wired' if d['id']=='WIRE' else d['id'].lower()):len(d['supply_pins'])*d['per_connection_budget_ma']/1000 for d in contract['power']['domains']}
power=3.3*sum(budgets.values())
bounce=[dict(inductance_nh=l,step_ma=i,edge_ps=dt,unmitigated_bounce_v=l*1e-9*i*1e-3/(dt*1e-12)) for l in (.2,1,2) for i in (5,20) for dt in (100,500)]
reservoir=[dict(step_ma=i,interval_ns=dt,droop_mv=20,ideal_cap_pf=i*1e-3*dt*1e-9/.02*1e12) for i in (5,20) for dt in (.1,.5,1)]
# Audit the optimistic assumptions against retained circuit evidence; do not
# silently replace a different VCO topology's sensitivity with this DC slope.
vco_path=PROJECT/'evidence/vco-supply-screen.json'
vco=json.loads(vco_path.read_text())
supply_k=max(abs(x) for x in vco['local_slopes_hz_per_v'])
supply_phase=[dict(offset_hz=f,ripple_peak_v=v,k_hz_per_v=g,
    uncorrected_phase_rms_rad=g*v/(math.sqrt(2)*f))
    for g in (10e6,supply_k) for f in (1e6,5e6,10e6) for v in (.001,.01)]
rf_floor=[]
for signal_dbm in (-56.86,-66.86,-76.86):
    for nf in (5.,10.,15.):
        floor=noise_dbm+nf
        rf_floor.append(dict(signal_dbm=signal_dbm,noise_figure_db=nf,
            noise_dbm=floor,thermal_noise_only_evm=10**((floor-signal_dbm)/20)))
package_reactance=[dict(carrier_hz=f,inductance_nh=l,series_reactance_ohm=2*math.pi*f*l*1e-9)
    for f in (2.4e9,2.5e9) for l in (.2,1.,5.)]
pad_reactance=[dict(carrier_hz=2.437e9,capacitance_pf=c,
    shunt_reactance_magnitude_ohm=1/(2*math.pi*2.437e9*c*1e-12)) for c in (.2,1.,3.)]
tuning_path=PROJECT/'evidence/vco-capture-tuning.json'
tuning=json.loads(tuning_path.read_text())
cascade=[]
for gain_db,nf_db in ((9.6,4.9),(12.,7.9)):
    # Friis: passive input loss at reference temperature, then LNA and lumped
    # downstream receiver. Only LNA numbers are measured other-process data.
    loss_db=2.;downstream_nf_db=15.
    factor=10**(loss_db/10)*(10**(nf_db/10)+(10**(downstream_nf_db/10)-1)/10**(gain_db/10))
    cascade.append(dict(lna_gain_db=gain_db,lna_nf_db=nf_db,
        assumed_pre_lna_loss_db=loss_db,assumed_downstream_nf_db=downstream_nf_db,
        inferred_total_nf_db=10*math.log10(factor),
        scope='Measured TSMC180 LNA precedent plus assumed matched power-gain/noise stages; not GF180 or measured complete receiver.'))
analog_audit=dict(
    literature_informed_receiver_cascades=cascade,
    lna_precedent_source='https://ethesys.lis.nsysu.edu.tw/ETD-db/ETD-search-c/view_etd?URN=etd-0919123-233952',
    process_interpretation=dict(verdict='No process-wide impossibility established by this audit',
        candidate_failures_are_not_process_limits=True,
        missing_characterization_is_not_failure=True,
        historical_supply_slope_is_not_an_achievable_lower_bound=True,
        pad_package_values_are_scenarios_not_measurements=True),
    external_clock_scenarios=[dict(carrier_hz=2.437e9,external_jitter_ps=.5,
        input_added_jitter_ps=j,distribution_added_jitter_ps=1.,
        total_uncorrelated_jitter_ps=math.sqrt(.5**2+j**2+1.),
        equivalent_phase_rms_rad=2*math.pi*2.437e9*1e-12*math.sqrt(.5**2+j**2+1.),
        scope='Assumed independent integrated timing errors over one common bandwidth; not measured GF180 jitter, a phase-noise mask or packet EVM prediction.')
        for j in (.5,1.,3.,10.)],
    external_support_risk_partition=dict(
        potentially_bypassed='Local oscillator only when a qualified direct external-LO/clock path is selected; external reference alone is insufficient.',
        retained=['input/ESD loading','clock receiver and distribution noise','required quadrature/division','incoming serial CDR','RF conversion/converter/driver performance'],
        analog_pad_dc_rating_a=.010,
        pad_source='https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html',
        pad_scope='Standard asig_5p0 cell rating, not a universal RF peak-current or bandwidth limit.'),
    mim_area_scenarios=[dict(capacitance_nf=c,density_ff_per_um2=d,
        ideal_plate_area_mm2=c/d,scope='Plate area only; one process option, excludes routing/spacing/ESR/ESL')
        for c in (.1,1.) for d in (1.,1.5,2.)],
    mim_source='https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html',
    loaded_vco_tuning=dict(source='evidence/vco-capture-tuning.json',
        source_sha256=hashlib.sha256(tuning_path.read_bytes()).hexdigest(),
        positive_and_negative_slopes=any(x>0 for x in tuning['slopes_hz_per_v']) and any(x<0 for x in tuning['slopes_hz_per_v']),
        slopes_hz_per_v=tuning['slopes_hz_per_v'],limitations=tuning['limitations'],
        model_assumption='Pulse PLL uses constant positive 200 MHz/V and +/-1 V tuning; physical branch and control range are not established.'),
    oscillator_supply=dict(model_hz_per_v=10e6,historical_dc_slope_hz_per_v=supply_k,
        ratio=supply_k/10e6,source='evidence/vco-supply-screen.json',
        source_sha256=hashlib.sha256(vco_path.read_bytes()).hexdigest(),
        scope='Historical transistor candidate local DC slope near 3.3 V, not measured silicon or an RF transfer function.'),
    supply_phase_scenarios=supply_phase,
    receiver_thermal_floor=rf_floor,
    tx_retained_case_margins=dict(current_limit_a=.028,peak_current_a=.02631193677,
        remaining_peak_current_a=.028-.02631193677,
        minimum_rail_v=3.169463,headroom_per_rail_v=.3,peak_open_differential_v=2.368074,
        remaining_differential_headroom_v=3.169463-2*.3-2.368074,
        scope='Arithmetic from one retained loaded TX fixture; no process/load/crest-factor envelope.'),
    package_series_reactance=package_reactance,pad_shunt_reactance=pad_reactance,
    limitations=['Supply phase values omit PLL suppression and receiver tracking; they are open-loop sinusoidal susceptibility, not payload EVM predictions.',
        'Thermal floor excludes conversion distortion, phase noise, blockers and ADC noise; gain cannot recover the lost input SNR.',
        'Package/pad reactances are exploratory lumped examples, not a measured network, insertion loss, or matched-port prediction.',
        'Default finite oscillator noise covers eight discrete tones at 250 kHz through 2 MHz, not a calibrated broadband phase-noise mask.'])
r=dict(status='conditional_analytic_scenarios_not_qualification',temperature_k=T,
    analog_assumption_audit=analog_audit,lo_residual_phase_scenarios=lo,baseband_aperture_jitter_scenarios=jitter,
    converter_thermal_lower_bounds=converters,thermal_noise_20mhz_dbm=noise_dbm,receiver_sensitivity_scenarios=sensitivity,
    receiver_reference_plane_scenarios=reference_planes,gain_noise_reference_scenarios=noise_gain,
    planning_current_a=budgets,sum_planning_current_a=sum(budgets.values()),sum_planning_power_at_3p3_v_w=power,
    thermal_scenarios=[dict(theta_ja_k_per_w=theta,rise_k=theta*power) for theta in (10,30,60,100)],
    supply_inductance_scenarios=bounce,ideal_local_reservoir_scenarios=reservoir,
    assumptions=['EVM values, NF, required SNR, package inductance and thetaJA are exploratory scenarios, not frozen specs or validated bounds.',
      'LO phase allocation uses 25% of total EVM power; equivalent time is not a full phase-noise mask or PLL requirement.',
      'Aperture jitter evaluated at baseband frequency, not the RF carrier; independent sampling and LO error budgets.',
      'Sampling C assumes two independent kT/C legs and thermal RMS <= half quantization RMS. Other circuit noise and settling excluded.',
      '350 mA is a sum of unqualified planning ceilings, not measured current or safe pad/package capacity.',
      'L di/dt omits decoupling/resonance; I dt/C omits ESR/ESL. Neither predicts the actual PDN.',
      'Reference-plane scenarios assume 20 MHz equivalent noise bandwidth and ideal linear conversion into 1 Vpp differential I/Q ranges; no matching, loading, mixer sideband or actual gain/NF calibration is inferred.',
      'Gain-noise scenarios isolate frontend versus excess ADC ENOB noise; ideal quantization, filters, clock error, blockers and channel estimation remain additional.',
      'No finite sensitivity sweep proves tolerance of an unknown physical quantity with no justified bound.'],
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
assert abs(power-1.155)<1e-12
assert all(lo[i]['equivalent_time_rms_ps']>lo[i+1]['equivalent_time_rms_ps'] for i in range(len(lo)-1))
assert abs(converters[-1]['diff_sampling_cap_per_leg_pf']/converters[-2]['diff_sampling_cap_per_leg_pf']-16)<1e-10
(PROJECT/'evidence/feasibility-bounds.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(lo=lo,converters=converters,power_w=power,thermal_noise_dbm=noise_dbm),indent=2))
