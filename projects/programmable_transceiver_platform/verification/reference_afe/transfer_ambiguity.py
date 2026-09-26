"""Propagate measurement-compatible transfer ambiguity through the RF reduction.
This is a sensitivity experiment, not a calibrated transistor or RF model.
"""
import copy,hashlib,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'system_model/connected'))
sys.path.insert(0,str(root/'verification'))
from adc_impairments import ADCImpairments
from full_chip_model import make_chip
source=root/'evidence/reference-afe-figure7-screen.json'
figure=json.loads(source.read_text())['conditional_shape_comparison']
a=10**(np.array(figure['target_harmonics_dbc'])/20)
x=np.cos(2*np.pi*np.arange(4096)/4096)
rows=[]
chip=make_chip(protocol='wifi_he20');service=chip.protocol_service;wave=service.waveform()
chip.output_network.configure(True,False)
for amplitude in [.05,.1,.2]:
    chip.adc_impairments=None
    clean=service.project_clocked_link(wave,bits=12,amplitude=amplitude,substeps=2)
    baseline=np.asarray(clean['samples'])
    for curve in figure['nonunique_monotone_transfers']:
        coefficients=a*np.array(curve['harmonic_signs'])
        impairment=ADCImpairments(odd_chebyshev=coefficients)
        # Independent Chebyshev evaluation and coherent sine-spectrum check.
        sampled=np.array([impairment.sample(complex(v,0)).real for v in x])
        expected=np.polynomial.chebyshev.chebval(x,[0,1,0,coefficients[0],0,coefficients[1],0,coefficients[2]])
        assert np.max(abs(sampled-expected))<1e-14
        spectrum=abs(np.fft.rfft(sampled));db=20*np.log10(spectrum[[3,5,7]]/spectrum[1])
        assert max(abs(db-np.array(figure['target_harmonics_dbc'])))<1e-9
        chip.adc_impairments=impairment
        held=impairment.held;state=impairment.rng.getstate()
        result=service.project_clocked_link(wave,bits=12,amplitude=amplitude,substeps=2)
        assert impairment.held==held and impairment.rng.getstate()==state and chip.time==0
        y=np.asarray(result['samples'])
        gain=np.vdot(baseline,y)/np.vdot(baseline,baseline)
        error=y-gain*baseline
        relative=float(np.sqrt(np.mean(abs(error)**2)/np.mean(abs(gain*baseline)**2)))
        rows.append(dict(tx_amplitude_setting=amplitude,harmonic_signs=curve['harmonic_signs'],
            gain_removed_difference_percent=relative*100,fitted_gain_magnitude=float(abs(gain)),
            clean_clipped_samples=clean['adc_clipped_samples'],impaired_clipped_samples=result['adc_clipped_samples'],samples=len(y)))
# Isolate analog-transfer ambiguity from the low-level quantization differences
# in the complete chain. Normalize the same RF fixture at the ADC input.
analog_rows=[]
for peak in [.3,.6,.9]:
    samples=wave.samples/max(max(abs(wave.samples.real)),max(abs(wave.samples.imag)))*peak
    for curve in figure['nonunique_monotone_transfers']:
        observer=ADCImpairments(odd_chebyshev=a*np.array(curve['harmonic_signs']))
        converted=np.array([observer.sample(v) for v in samples])
        gain=np.vdot(samples,converted)/np.vdot(samples,samples)
        delta=converted-gain*samples
        relative=float(np.sqrt(np.mean(abs(delta)**2)/np.mean(abs(gain*samples)**2)))
        analog_rows.append(dict(normalized_axis_peak=peak,harmonic_signs=curve['harmonic_signs'],gain_removed_difference_percent=relative*100))
# Keep the table's SNR separate from the figure's harmonics: their measurement
# conditions are not established as identical. Unknown tone normalization changes
# the absolute noise assigned to a fixed converter full scale.
audit_path=root/'evidence/reference-afe-measurement-audit.json'
audit=json.loads(audit_path.read_text())
snr=audit['paper']['adc']['snr_at_20msps_db']
noise_rows=[]
for tone_peak in [.1,.5,1.]:
    sigma=tone_peak/np.sqrt(2)*10**(-snr/20)
    for peak in [.3,.6,.9]:
        samples=wave.samples/max(max(abs(wave.samples.real)),max(abs(wave.samples.imag)))*peak
        m=ADCImpairments(noise_rms=float(sigma),seed=731)
        converted=np.array([m.sample(v) for v in samples])
        delta=converted-samples
        predicted=np.sqrt(2*sigma**2/np.mean(abs(samples)**2))
        observed=np.sqrt(np.mean(abs(delta)**2)/np.mean(abs(samples)**2))
        # Independent I/Q noise each has variance sigma squared.
        assert abs(observed/predicted-1)<.06
        noise_rows.append(dict(assumed_characterization_tone_axis_peak=tone_peak,
            rf_waveform_axis_peak=peak,noise_rms_per_axis=float(sigma),
            predicted_noise_over_signal_percent=float(predicted*100),
            realized_noise_over_signal_percent=float(observed*100),samples=len(samples)))
# Tangent continuation is continuous and remains increasing outside normalized rails.
for signs in figure['nonunique_monotone_transfers']:
    m=ADCImpairments(odd_chebyshev=a*np.array(signs['harmonic_signs']))
    values=[m.sample(complex(v,0)).real for v in [-1.1,-1.000001,-1,-.999999,.999999,1,1.000001,1.1]]
    assert all(b>v for v,b in zip(values,values[1:]))
print(json.dumps(dict(noise_normalization_scenarios=noise_rows,unquantized_adc_waveform_cases=analog_rows,cases=rows,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,audit_path,root/'system_model/connected/adc_impairments.py',Path(__file__)]},
 limitations=['All eight curves match only three conditional harmonic magnitudes of the reference-AFE figure. Harmonic identity and absolute normalization remain assumptions.',
 'Same static per-axis transfer is assigned to I/Q as a sensitivity; not recovered transceiver ADC coefficients.',
 'Frozen-rail HE20 waveform projection,12bit quantization,no extra noise. Difference is against the clean chain after fitted gain removal, not standard packet EVM or compliance.',
 'Unquantized cases isolate analog transfer on the HE20 fixture, with declared ADC-axis peak; chain cases also include quantization differences. Neither is standard-compliance EVM.',
 'Assigned source amplitudes explore operating level; none is identified as the measured AFE tone level.',
 'Noise-only scenarios use table SNR separately from figure harmonics. They assume white independent I/Q noise, unchanged integrated noise at the RF fixture sampling rate, and linear unity conversion. Unknown measurement bandwidth, filtering and noise spectrum prevent calibration. No quantizer or clipping is applied in these noise-only comparisons.',
 'Passing this experiment proves ambiguity propagation, not physical feasibility. Default ADC behavior remains unchanged.']),indent=2))
