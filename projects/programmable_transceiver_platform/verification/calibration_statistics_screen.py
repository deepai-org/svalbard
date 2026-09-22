"""Independent coverage and negative controls for fixed-window calibration."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from calibration_statistics import assess_samples

options=dict(planned_samples=64,confidence=.999,noise_sigma_v=.001,
    systematic_bound_v=1/4096,gain_interval=(.95,1.05),tolerance_v=.001,
    assumptions_validated=True)
zero=assess_samples([0.]*64,**options)
assert zero['statistical_pass'] and not zero['valid']
assert not assess_samples([0.],**options)['statistical_pass']
for key,value in [('assumptions_validated',False),('clipped',True),('quiet',False),
                  ('observation_epoch',1),('range_limited',True),('noise_sigma_v',None)]:
    row=assess_samples([0.]*64,**(options|{key:value}))
    assert not row['statistical_pass'] and not row['valid']
assert assess_samples([.003]*64,**options)['accuracy']=='statistical_failure'
assert not assess_samples([.0008]*64,**options)['statistical_pass']
# Coverage is measured against independently generated residual + gain + noise,
# not by comparing two implementations of the same confidence interval.
rng=np.random.default_rng(20260921)
cases=[]
for residual,gain,bias in [(0.,1.,0.),(.0009,.95,1/4096),(-.0009,1.05,-1/4096),(.003,1.,0.)]:
    observations=gain*residual+bias+rng.normal(0,.001,(10000,64))
    covered=passed=0
    for samples in observations:
        result=assess_samples(samples,**options)
        lo,hi=result['residual_confidence_interval_v']
        covered+=lo<=residual<=hi
        passed+=result['statistical_pass']
        assert not result['valid']
    assert covered>=9970
    if abs(residual)>.001:assert passed==0
    cases.append(dict(residual_v=residual,gain=gain,bias_v=bias,windows=10000,
                      covered=int(covered),statistically_qualified=int(passed)))
report=dict(status='passed',zero_case=zero,cases=cases,
    model_sha256=hashlib.sha256((P/'system_model/connected/calibration_statistics.py').read_bytes()).hexdigest(),
    limitations=['Synthetic independent Gaussian observation model only; physical assumptions not established.',
      'Not yet connected to repeated shared-ADC scheduling or host status.',
      'Per-window confidence does not cover repeated retries or a lifetime of calibrations.'])
(P/'evidence/calibration-statistics-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
