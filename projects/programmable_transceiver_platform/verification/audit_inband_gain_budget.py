"""Conditional gain/noise arithmetic; never combine separate fixtures into measured SNR."""
import hashlib,json,math
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths={n:P/'evidence'/n for n in ['bb-inband.json','bb-noise.json']}
a=json.loads(paths['bb-inband.json'].read_text());n=json.loads(paths['bb-noise.json'].read_text())
tone=next(c for c in a['cases'] if c['name']=='tone');assert tone['completed'] and n['completed']
f=next(x for x in tone['fits'] if x['window_ns']==[800,1200] and x['harmonic_order']==8)
step=2/256;quant=step/math.sqrt(12);rows=[]
for channel in ('i','q'):
 peak=f[channel+'_peak_v'];cases=[]
 for nc in n['cases']:
  if not nc['name'].startswith('filter_'):continue
  noise=nc['output_rms_v_1k_20meg_trapezoid']
  cases.append(dict(noise_fixture=nc['name'],assumed_noise_rms_v=noise,
   conditional_signal_to_filter_fixture_noise_db=20*math.log10(peak/math.sqrt(2)/noise),
   gain_to_make_ideal_adc_quantization_rms_equal_assumed_filter_noise=quant/noise))
 rows.append(dict(channel=channel,measured_peak_v=peak,nominal_adc_peak_steps=peak/step,
  illustrative_output_targets=[dict(target_peak_v=v,required_post_filter_gain=v/peak,
   ideal_adc_only_sine_snr_db=20*math.log10(v/math.sqrt(2)/quant)) for v in (.125,.25,.5)],noise_scenarios=cases))
out=dict(status='conditional_budget_not_receiver_noise_measurement',sources_sha256={k:sha(v) for k,v in paths.items()},
 nominal_adc_step_v=step,ideal_quantization_rms_v=quant,cases=rows,
 decision='Allocate gain placement and input-referred noise together; post-filter gain alone cannot improve existing analog SNR.',
 limitations=['Tone and noise are different fixtures: RF-driven time-varying receiver versus DC-linearized filter atCM0.9V and1kohm noisy source legs.',
 '1kHz–20MHz noise integration is diagnostic, not qualified sampling bandwidth or an alias/noise-folding calculation.',
 'The two model-noise options are scenarios, not bounds or measured silicon.',
 'ADC quantization formula assumes an ideal uniform converter with uncorrelated quantization error; not valid measured SNR for current sub-LSB coherent input.',
 'Illustrative output targets are design scenarios, not adopted requirements; gain headroom, compression, bandwidth, added noise and power remain unverified.',
 'Matched receiver zero control pending; complete receiver noise includes other missing sources.'])
(P/'evidence/inband-gain-budget.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(rows,indent=2))
