"""Measurement-facing residuals and identifiability; no fit or pass-count score."""
import hashlib,json,math,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'system_model/connected'))
from capacitor_network import CapacitorNetwork
p=root/'evidence/reference-afe-amplifier-sim.json'
amp=json.loads(p.read_text())
release_path=root/'evidence/reference-afe-release-audit.json'
release=json.loads(release_path.read_text())
pad_path=root/'evidence/reference-afe-pad-routing.json'
pads=json.loads(pad_path.read_text())
for name,top in release['amplifier_baseline_audit']['external_bias_evidence']['connections'].items():
 assert any(r['cell']=='opamp2_to_fix' and r['label']==name and top in r['top_labels'] for r in pads['amplifier_terminals'])
measured={'gain_db':92.,'gbw_mhz':12.5,'power_upper_mw':10.}
author_sim={'gain_db':99.,'gbw_mhz':14.,'power_mw':5.}
comparisons=[]
for case in amp['cases']:
 if case.get('unity_gain_hz') is None:continue
 comparisons.append(dict(configuration={k:case[k] for k in ['output_node','vbiasn_v','vbiasp_v','load_pf','compensation_scale']},
   gain_db=case['low_frequency_gain_db'],gbw_mhz=case['unity_gain_hz']/1e6,
   gain_error_vs_measured_db=case['low_frequency_gain_db']-measured['gain_db'],
   gbw_error_vs_measured_percent=100*(case['unity_gain_hz']/1e6/measured['gbw_mhz']-1),
   gain_error_vs_author_sim_db=case['low_frequency_gain_db']-author_sim['gain_db'],
   gbw_error_vs_author_sim_percent=100*(case['unity_gain_hz']/1e6/author_sim['gbw_mhz']-1)))
closest_bw=min(comparisons,key=lambda r:abs(r['gbw_error_vs_measured_percent']))
# Illustrative dominant-pole equivalent: A=gm/go and fu=gm/(2piC).
# A simultaneous gm,C,go rescaling leaves both observations unchanged.
jacobian=np.array([[1,0,-1],[1,-1,0]])
assert np.linalg.matrix_rank(jacobian)==2 and np.all(jacobian@np.ones(3)==0)
equivalents=[]
for c in [5e-12,10e-12]:
 gm=2*math.pi*12.5e6*c;go=gm/10**(92/20)
 equivalents.append(dict(equivalent_capacitance_pf=c*1e12,effective_gm_ms=gm*1e3,effective_output_resistance_mohm=1/go/1e6))
sndr=6.02*4.27+1.76
noise=10**(-41/20);distortion=math.sqrt(10**(-sndr/10)-noise**2)
# Conditional necessary bounds, not estimates: independent noise powers add.
# Two independent sampled legs give differential variance 2*k*T/C per-leg.
temperature=300.;boltzmann=1.380649e-23
noise_bounds=[]
for differential_peak in [.3,1.53,3.]:
 signal_rms=differential_peak/math.sqrt(2)
 noise_rms=signal_rms*noise
 noise_bounds.append(dict(assumed_differential_tone_peak_v=differential_peak,
  total_input_referred_noise_rms_v=noise_rms,
  minimum_per_leg_sampling_capacitance_f=2*boltzmann*temperature/noise_rms**2))
jitter_bounds=[dict(assumed_tone_hz=f,
 maximum_rms_aperture_jitter_s=noise/(2*math.pi*f)) for f in [5e6,10e6]]
noise_identifiability=dict(assumed_temperature_k=temperature,
 assumptions=['41dB SNR represents total noise relative to a sinusoidal signal, excluding harmonics.',
 'Input-referred unity sampling gain, independent thermal noise in equal sampling capacitors, and no noise cancellation or filtering.',
 'Small independent aperture jitter; tone frequencies below are scenarios, not recovered table conditions.'],
 amplitude_scenarios=noise_bounds,jitter_scenarios=jitter_bounds,
 interpretation='These are necessary lower bounds on C and upper bounds on jitter only under the stated model. Other noise sources make the limits stricter. They do not identify actual capacitance, aperture jitter, oscillator phase noise or measurement bandwidth.',
 limitation='Unknown tone amplitude removes an absolute capacitance bound from the publication alone. Unknown table tone frequency prevents a numerical measured jitter bound. Correlation, filtering and noise definitions can invalidate the simple decomposition.')
# Monotonic differential CDAC: each normalized weight moves one leg by
# weight*reference_span. Even all decisions of one sign sum to only that span.
geometry_path=root/'evidence/reference-afe-cap-geometry.json'
geometry=json.loads(geometry_path.read_text())
cap=np.array([geometry['bit_geometry'][f'B{i}']['m3_m4_overlap_um2'] for i in range(13)])*.0394e-15
weights=cap/sum(cap)
reference_span=2.5-.8
maximum_correction=float(sum(weights)*reference_span)
assert abs(maximum_correction-1.7)<1e-14
# Independently solve the extreme topology using the capacitor matrix.
names=['top']+[f'b{i}' for i in range(13)]
net=CapacitorNetwork(names,[('top',f'b{i}',float(c)) for i,c in enumerate(cap)])
initial=dict(top=1.65,**{f'b{i}':2.5 for i in range(13)})
final,_=net.step(initial,{f'b{i}':.8 for i in range(13)})
assert abs((initial['top']-final['top'])-maximum_correction)<1e-13
# A benign memoryless saturation example quantifies the consequence of mixing
# the sensor-board references with an assumed full6Vpp characterization tone.
phase=np.arange(16384)*2*np.pi*137/16384
signal=3*np.sin(phase);limited=np.clip(signal,-maximum_correction,maximum_correction)
power=abs(np.fft.rfft(limited))**2;fundamental=power[137];power[0]=0;power[137]=0
range_check=dict(sensor_board_reference_high_v=2.5,sensor_board_reference_low_v=.8,
 maximum_ideal_differential_correction_v=maximum_correction,
 maximum_ideal_differential_range_vpp=2*maximum_correction,
 published_range_vpp=6,
 minimum_reference_span_for_unattenuated_6vpp_v=3,
 maximum_input_transfer_gain_to_fit_6vpp_at_sensor_references=maximum_correction/3,
 clipping_example=dict(input_vpp=6,output_limit_v=maximum_correction,
  clipped_sample_fraction=float(np.mean(abs(signal)>maximum_correction)),
  noiseless_sndr_db=float(10*np.log10(fundamental/sum(power))),
  sfdr_db=float(10*np.log10(fundamental/max(power)))),
 interpretation='The reconstructed direct-sampled monotonic array with2.5/0.8V references does not cover6Vpp differential input. Figure9 sensor-board references are not established ADC characterization settings; the table range is not the FFT tone amplitude.',
 limitations=['Area-only normalized weights and unity sampled-input transfer; no measured full-transfer reproduction.',
 'Additional top-to-ground capacitance reduces DAC correction under direct top-plate sampling; it does not independently expand this range.',
 'Different references or input attenuation could change the range. Neither is inferred as the actual characterization setup.',
 'Clipping example is not a fit to measured ADC spectrum and does not establish that the fabricated ADC clipped.'])
report=dict(
 paper=dict(url='https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957346',location='Tables1-2, printed54; amplifier conditions printed52-53; Figure7 printed54.',
   measured_amplifier=measured,authors_amplifier_simulation=author_sim,
   adc=dict(functional_rate_msps='>30',enob_at_20msps=4.27,snr_at_20msps_db=41,sfdr_db=33.7,input_range_vpp=6),
   measurement_conditions_unidentified=['Amplifier external cascode biases, output loading/measurement plane and phase margin.', 'ADC FFT input amplitude, source/reference impedances, bias/calibration settings and raw code records.', 'Figure7 Nyquist input near4.99MHz is not established as the same test as20MS/s table metrics.']),
 amplifier_baseline_provenance=release['amplifier_baseline_audit'],
 amplifier_comparisons=comparisons,
 closest_bandwidth_case=closest_bw,
 identifiability=dict(equivalent_model='A=gm/go; fu=gm/(2*pi*C). Illustrative, not the reconstructed two-branch compensation circuit.',
   log_parameter_order=['gm','C','go'],log_observable_order=['gain','unity_frequency'],jacobian=jacobian.tolist(),rank=2,unobservable_scaling_direction=[1,1,1],
   indistinguishable_equivalent_examples=equivalents,
   conclusion='Even exact gain and bandwidth do not identify gm,C,go independently. Actual topology, known passives and additional observables are needed; missing bench conditions add ambiguity.'),
 adc_range_consistency=range_check,
 adc_noise_identifiability=noise_identifiability,
 adc_normalized_constraints=dict(sndr_db=sndr,noise_over_signal_rms=noise,distortion_over_signal_rms=distortion,
   condition='ENOB-to-SNDR convention and compatible measurement conditions assumed. Absolute voltage errors scale with unknown tone amplitude.',
   uniquely_identified_physical_parameters=[]),
 decisions=['Do not calibrate physical parasitics to a single matching metric. The bandwidth-matching amplifier scenario misses measured gain by about24.5dB.',
 'Resolve reconstructed-vs-author-simulation discrepancy before attributing differences to fabricated device physics.',
 'Reference-sequence agreement is a simulation-to-simulation surrogate check; it is not measurement validation.',
 'Next silicon-facing ADC comparison must jointly address noise,total distortion,largest spur and functional timing without assuming the table andFigure7 share conditions.',
 'No measured GHz fT/fmax,RF NF or PLL phase noise is supplied by this AFE. Do not upgrade transceiver RF/clock assumptions based on local reference-driver success.'],
 source_sha256={source.name:hashlib.sha256(source.read_bytes()).hexdigest() for source in [p,release_path,pad_path,geometry_path,root/'system_model/connected/capacitor_network.py',Path(__file__)]})
print(json.dumps(report,indent=2))
