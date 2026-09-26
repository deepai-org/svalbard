"""Conditional binary-DAC ratio screen; not an extracted SAR simulation.
Enumerates every code to avoid interpreting relative LSB geometry as full-scale error.
"""
import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
j=json.loads((root/'evidence/reference-afe-cap-geometry.json').read_text())
a=np.array([j['bit_geometry'][f'B{i}']['m3_m4_overlap_um2'] for i in range(13)])
p=np.array([j['bit_geometry'][f'B{i}']['m3_perimeter_um'] for i in range(13)])
w=2.**np.arange(12,-1,-1)
codes=np.arange(8192)
bits=((codes[:,None]>>np.arange(12,-1,-1))&1)
ideal=codes/8191
rows=[]
# Edge coefficient is an exploratory assumption, not measured process data.
for edge in [0,.001,.005,.01,.02,.05]:
 cap=.0394*a+edge*p
 actual=bits@cap/cap.sum()
 error=actual-ideal
 rows.append(dict(edge_density_ff_per_um=edge,total_capacitance_ff=float(cap.sum()),
                  max_endpoint_inl_fullscale=float(abs(error).max()),
                  rms_endpoint_inl_fullscale=float(np.sqrt(np.mean(error**2))),
                  max_endpoint_inl_13bit_lsb=float(abs(error).max()*8191),
                  relative_weight_error=(cap/cap[0]/(w/w[0])-1).tolist()))
# Conditional discrepancy bound, not a conversion of DAC INL into ADC ENOB.
# If an ADC transfer had this maximum normalized error E, its RMS residual
# after removing DC/fundamental cannot exceed E. Sine RMS = A_pp/(2*sqrt(2)).
measured_sndr_db=6.02*4.27+1.76
noise_power=10**(-41/10)
distortion_ratio=np.sqrt(10**(-measured_sndr_db/10)-noise_power)
worst=max(r['max_endpoint_inl_fullscale'] for r in rows)
quantization_half_step=.5/8191
bounds=[]
for amplitude_pp_fraction in [1.,.5,.1]:
 signal_rms=amplitude_pp_fraction/(2*np.sqrt(2))
 required=signal_rms*distortion_ratio
 bounds.append(dict(sine_peak_to_peak_fraction_of_range=amplitude_pp_fraction,
   distortion_rms_required_fullscale=float(required),
   hypothetical_error_ceiling_including_half_lsb=worst+quantization_half_step,
   required_rms_to_hypothetical_max_error_ratio=float(required/(worst+quantization_half_step))))
print(json.dumps(dict(source_sha256=j['source_sha256'],scenarios=rows,
 measured_distortion_discrepancy=dict(distortion_rms_relative_to_signal=float(distortion_ratio),scenarios=bounds,
 maximum_sine_pp_fraction_explainable_under_hypothetical_bound=float((worst+quantization_half_step)*2*np.sqrt(2)/distortion_ratio),
 scope='Only if this DAC-error envelope also bounded the ADC transfer; actual SAR sequence and capacitance matrix are not established. Not a silicon bound.'),
 assumptions=['B0..B12 assigned descending binary weights; controller mapping not yet verified.',
              'Endpoint-normalized DAC voltage, not ADC ENOB or EVM.',
              'Scalar area+perimeter approximation; no capacitance matrix, reference dynamics or inter-bit coupling.',
              'No implicit identification of missing dummy plate or differential switching sequence.',
              'Edge coefficient sweep is exploratory, not a confidence interval.'],
 conclusion='Evaluate full-scale transfer error before attributing measured ADC distortion to small-bit geometry.'),indent=2))
