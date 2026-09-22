"""Check ensemble tone power after linear PLL shaping versus dense integration."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from three_cap_thermal_noise import spectrum
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from three_cap_resistor_noise import ResistorNoiseFilter
from three_cap_retuning_clock import BALANCED_FILTER
source=P/'evidence/stressed-three-cap-quality-mode1-launch.json'
m=json.loads(source.read_text());rows=[]
for name,v,ip,kv in [('nominal',BALANCED_FILTER,100e-6,200e6),('stressed',m['filter_values'],100e-6*m['gain_scales']['icp'],200e6*m['gain_scales']['kvco'])]:
 f=np.geomspace(100,1e7,32000)
 ref=float(np.trapezoid(spectrum(f,v,300,True,icp=ip,kvco=kv).sum(axis=1)*(kv/f)**2,f))
 for n in (32,64,128,256):
  model=ResistorNoiseFilter(noise_bins=n,**v)
  frequencies=model.noise_frequency
  # PSD divided by current PSD gives each resistor's voltage transfer squared.
  current_psd=np.array([4*1.380649e-23*300/v[k] for k in ('r','r3')])
  gain2=spectrum(frequencies,v,300,True,icp=ip,kvco=kv)/current_psd
  power=float(np.sum(gain2*(model.noise_amplitude.T**2/2)*(kv/frequencies[:,None])**2))
  rows.append(dict(case=name,bins=n,phase_rms_rad=float(np.sqrt(power)),relative_variance_error=power/ref-1))
 assert abs(rows[-1]['relative_variance_error'])<.001
report=dict(status='linear_ensemble_resolution_checked',rows=rows,
 limitations=['Ensemble power only: a finite-window seeded realization can differ.',
 'Does not test nonlinear fractional PLL, sampled aliasing, or coupled TX quality.'],
 source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,Path(__file__),P/'verification/three_cap_thermal_noise.py',P/'system_model/connected/three_cap_resistor_noise.py')})
(P/'evidence/resistor-noise-resolution.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
