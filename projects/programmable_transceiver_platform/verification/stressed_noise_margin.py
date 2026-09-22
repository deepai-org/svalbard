"""Conditional error-budget audit, not a coupled stochastic acceptance test."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from three_cap_thermal_noise import spectrum,K
P=Path(__file__).resolve().parents[1]
launch=P/'evidence/stressed-three-cap-quality-mode1-launch.json'
quality=P/'evidence/connected-limited-rail20-pad-quality-mode1-three-cap-stressed-repeated-cal-phase-diagnostic.json'
m=json.loads(launch.read_text());q=json.loads(quality.read_text())
assert m['status']=='passed' and hashlib.sha256(quality.read_bytes()).hexdigest()==m['result_sha256']
v=m['filter_values'];icp=100e-6*m['gain_scales']['icp'];kvco=200e6*m['gain_scales']['kvco']
f=np.geomspace(.01,1e12,30000)
measured=float(np.trapezoid(spectrum(f,v,300,False).sum(axis=1),f))
expected=K*300*(1/v['c3']-1/sum(v[k] for k in ('cf','cs','c3')))
assert abs(measured/expected-1)<1e-3
est=[]
for n in (4000,8000):
 f=np.geomspace(100,1e7,n)
 psd=spectrum(f,v,300,True,icp=icp,kvco=kvco,divider=2437/40)*(kvco/f[:,None])**2
 est.append(float(np.sqrt(np.trapezoid(psd.sum(axis=1),f))))
assert abs(est[1]/est[0]-1)<1e-5
base=q['transmit_quality']['corrected_relative_rms'];limit=q['transmit_quality']['screen_budget']
headroom=math.sqrt(max(0,limit**2-base**2))
report=dict(status='conditional_budget_estimate',baseline_tx_error=base,screen_limit=limit,
 independent_additive_rms_headroom=headroom,resistor_phase_rms_rad=est[-1],
 conditional_quadrature_tx_error=math.hypot(base,est[-1]),
 thermal_to_headroom_ratio=est[-1]/headroom,
 equilibrium_relative_error=measured/expected-1,
 inputs_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (launch,quality,Path(__file__),Path(__file__).with_name('three_cap_thermal_noise.py'))},
 limitations=['Quadrature comparison assumes independent small phase error mapped with unit sensitivity to normalized TX error.',
 'Gain fitting, finite observation window and analog filtering alter that mapping; this is not a pass/fail prediction.',
 'Averaged resistor noise only, 100 Hz to 10 MHz at 300 K; sampled aliasing, pump, reference and other device noise omitted.'])
(P/'evidence/stressed-noise-margin.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('inputs_sha256','limitations')},indent=2))
