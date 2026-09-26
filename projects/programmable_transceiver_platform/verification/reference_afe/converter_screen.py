"""Check independent noise/distortion constraints against measured GF180 evidence.
A cubic matching one spur cannot generally reproduce total measured distortion.
"""
import json
import math
from pathlib import Path
import sys
import numpy as np
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'system_model/connected'))
sys.path.insert(0,str(root/'verification'))
from adc_impairments import ADCImpairments

n=65536; k=997
t=np.arange(n)*2*np.pi*k/n
signal=np.sin(t)
# Constant transfer offset is DC, not a spectral spur. Quantization and clipping
# are explicit so comparator threshold errors are not automatically called THD.
offset_rows=[]
for amplitude in [.5,.9,.99]:
    for offset in [0.,.05,.15]:
        raw=amplitude*signal+offset
        clipped=np.clip(np.rint(raw*2048),-2048,2047)/2048
        spectrum=np.abs(np.fft.rfft(clipped))*2/n
        fundamental=spectrum[k]
        spectrum[0]=0;spectrum[k]=0
        residual_power=np.sum(spectrum[1:-1]**2)/2+spectrum[-1]**2/4
        offset_rows.append(dict(input_amplitude=amplitude,constant_offset=offset,
            clipped_fraction=float(np.mean((raw < -1)|(raw > 2047/2048))),
            sfdr_db=float(20*np.log10(fundamental/max(spectrum))),
            sndr_db=float(10*np.log10((fundamental**2/2)/residual_power))))
assert all(row['sndr_db']>65 for row in offset_rows if row['clipped_fraction']==0)
assert any(row['sndr_db']<40 for row in offset_rows if row['clipped_fraction']>0)
# Exact unquantized offset invariance after removing DC.
assert np.max(np.abs(np.fft.rfft(.5*signal+.15)[1:]-np.fft.rfft(.5*signal)[1:]))<1e-10

r=10**(-33.7/20)
cubic=-4*r/(1+3*r)
fitted=ADCImpairments(cubic=cubic)
y=np.array([fitted.sample(complex(v,0)).real for v in signal])
sp=np.abs(np.fft.rfft(y))*2/n
spur=float(sp[3*k]/sp[k])
assert abs(spur-r)<1e-12
sigma=(1+.75*cubic)/math.sqrt(2)*10**(-41/20)
model=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=731)
noisy=np.array([model.sample(complex(v,0)).real for v in signal])
fit=np.column_stack([np.sin(t),np.cos(t),np.ones(n)])
coef=np.linalg.lstsq(fit,noisy,rcond=None)[0]
residual=noisy-fit@coef
sndr=20*np.log10(np.hypot(*coef[:2])/math.sqrt(2)/np.std(residual))
# Noise realization must be invariant to how callers partition samples.
a=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=3)
b=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=3)
whole=[a.sample(complex(v,0)) for v in signal[:100]]
parts=[b.sample(complex(v,0)) for v in signal[:37]]+[b.sample(complex(v,0)) for v in signal[37:100]]
assert whole==parts
assert ADCImpairments().sample(.2+.7j)==.2+.7j
from adc_clipping_lifecycle import controls
from diagnostic_lifecycle import DiagnosticChip
controls()
a=DiagnosticChip();a.configure(0,0)
b=DiagnosticChip(adc_impairments=ADCImpairments(cubic=cubic));b.configure(0,0)
assert a.convert_adc(.8+.6j)==a.quantize_adc(.8+.6j)
assert b.convert_adc(.8+.6j)==b.quantize_adc(ADCImpairments(cubic=cubic).sample(.8+.6j))
assert a.convert_adc(.8+.6j)!=b.convert_adc(.8+.6j)

# Independent transparent-filter check: sampling precedes noise and quantization.
from protocol_signals import receiver_projection, Waveform
values=np.asarray([complex(.2+i*.01,-.1) for i in range(20)])
wave=Waveform(values,1e6,'test',np.array([]),{})
imp=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=193)
state=imp.rng.getstate()
projected,_=receiver_projection(wave,[1e15],[1.],amplitude=1.,sample_stride=4,adc_impairments=imp)
reference=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=193)
expected=np.asarray([reference.sample(v) for v in values[3::4]])
q=lambda v:np.clip(np.rint(v*2048),-2048,2047)/2048
assert np.array_equal(projected,q(expected.real)+1j*q(expected.imag))
assert imp.rng.getstate()==state

# The acquisition stage must satisfy the analytical RC step response, including
# history across samples. R and acquisition time are explicit scenario choices.
acquisition_rows=[]
for cap_pf in [.666,1.5,3.]:
    rc=ADCImpairments(sampling_r_ohm=1000.,sampling_c_f=cap_pf*1e-12,acquisition_s=2e-9)
    target=.8-.4j
    for count in range(1,6):
        got=rc.sample(target)
        expected=target*(1-math.exp(-count*2e-9/(1000*cap_pf*1e-12)))
        assert abs(got-expected)<1e-14
    acquisition_rows.append(dict(sampling_r_ohm=1000.,sampling_c_pf=cap_pf,acquisition_ns=2.,
                                first_sample_unsettled_fraction=math.exp(-2e-9/(1000*cap_pf*1e-12))))
for kwargs in [dict(sampling_r_ohm=1000),dict(sampling_r_ohm=1000,sampling_c_f=0,acquisition_s=2e-9)]:
    try:ADCImpairments(**kwargs)
    except ValueError:pass
    else:raise AssertionError('Invalid acquisition parameters accepted')
rc=ADCImpairments(sampling_r_ohm=1000,sampling_c_f=1.5e-12,acquisition_s=2e-9)
import copy
chunked=copy.deepcopy(rc)
values=[complex(v,0) for v in signal[:100]]
assert [rc.sample(v) for v in values]==[chunked.sample(v) for v in values[:37]]+[chunked.sample(v) for v in values[37:]]

from full_chip_model import make_chip
chain_rows=[]
for profile in ['wifi_he20','bluetooth_le','bluetooth_br_edr','ieee802154_24','lora_24']:
    chip=make_chip(protocol=profile,adc_impairments=ADCImpairments(cubic=cubic,noise_rms=sigma,seed=731,sampling_r_ohm=1000.,sampling_c_f=1.5e-12,acquisition_s=2e-9))
    service=chip.protocol_service;wave=service.waveform()
    chip.output_network.configure(True,False)
    state=chip.adc_impairments.rng.getstate();held_before=chip.adc_impairments.held
    impaired=service.project_clocked_link(wave,bits=12,substeps=2)
    repeat=service.project_clocked_link(wave,bits=12,substeps=2)
    assert np.array_equal(impaired['samples'],repeat['samples'])
    assert chip.adc_impairments.rng.getstate()==state and chip.time==0
    assert chip.adc_impairments.held==held_before
    chip.adc_impairments=None
    clean=service.project_clocked_link(wave,bits=12,substeps=2)
    delta=np.sqrt(np.mean(abs(impaired['samples']-clean['samples'])**2))
    assert delta>0
    chain_rows.append(dict(profile=profile,samples=len(impaired['samples']),
        adc_impairment_change_rms=float(delta),clipped_samples=impaired['adc_clipped_samples'],
        scope='Frozen-rail TX/pad/channel/RX/ADC projection; no packet or acquired-clock claim'))

print(json.dumps(dict(
 constant_offset_spectral_screen=offset_rows,
 acquisition_step_response=acquisition_rows,
 clocked_conversion_chain=chain_rows,
 clocked_adc_scenario=dict(sampling_r_ohm=1000.,sampling_c_f=1.5e-12,acquisition_s=2e-9,calibrated_to_silicon=False),
 measured=dict(enob=4.27,snr_db=41,sfdr_db=33.7),
 single_cubic_scenario=dict(cubic=cubic,input_referred_noise_rms=sigma,measured_fft_sfdr_db=-20*math.log10(spur),sndr_db=float(sndr),enob=float((sndr-1.76)/6.02)),
 target_sndr_from_enob_db=6.02*4.27+1.76,
 conclusion='One cubic spur plus the reported SNR does not reproduce the reported ENOB; additional distortion, definitions, or differing test conditions matter.',
 limitations=['Full-scale sine scenario, not a unique fit to silicon.',
 'Measured table lacks enough test-condition detail to identify coefficients or error spectrum uniquely.',
 'Noise and nonlinear transfer are optional in ReturnChip before quantization; defaults retain prior behavior.',
 'Finite acquisition uses a piecewise-constant input target and explicit R/C/time scenarios; no signal-dependent resistance or bootstrap calibration.',
 'Clocked chain verifies impairment propagation through the configured RF reduction; no new EVM, packet or physical qualification claim.']),indent=2))
