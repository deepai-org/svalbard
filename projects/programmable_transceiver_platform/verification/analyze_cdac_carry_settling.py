"""Post-transition residual envelopes; diagnostic thresholds, not ADC limits."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-carry-transition'
source=P/'evidence/cdac-carry-transition.json';d=json.loads(source.read_text());arrays={}
for case in d['cases']:
 p=W/(case['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat']
 a=np.loadtxt(p,skiprows=1);assert np.all(np.diff(a[:,0])>0) and np.isfinite(a).all();arrays[case['name']]=a
rows=[]
for initial in [127,128]:
 a=arrays[f'code{initial}_switch1'];b=arrays[f'code{initial}_switch0'];t=a[:,0]
 diff=a[:,1]-a[:,2]-np.interp(t,b[:,0],b[:,1]-b[:,2]);cm=(a[:,1]+a[:,2])/2-np.interp(t,b[:,0],(b[:,1]+b[:,2])/2)
 endpoint=float(np.interp(4.9e-9,t,diff));envelopes=[]
 for delay_ps in [0,50,100,200,500,1000]:
  lo=2.1e-9+delay_ps*1e-12;hi=4.9e-9
  tt=np.r_[lo,t[(t>lo)&(t<hi)],hi]
  differential=np.interp(tt,t,diff)-endpoint;common=np.interp(tt,t,cm)
  envelopes.append(dict(delay_after_gate_ramp_ps=delay_ps,max_differential_residual_v=float(max(abs(differential))),max_common_mode_motion_v=float(max(abs(common)))))
 rows.append(dict(initial_code=initial,settled_differential_step_v=endpoint,envelopes=envelopes))
report=dict(status='finite_post_ramp_settling_diagnostic',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),results=rows,limitations=['Residual is relative to4.9ns endpoint, not an independently verified infinite-time value.', 'Envelopes extend only until4.9ns before reverse transition.', 'Delay starts after ideal100ps gate ramp; physical driver timing and comparator decision aperture are not represented.', 'Ideal reference rails and reset comparator; no full SAR accuracy qualification.'])
(P/'evidence/cdac-carry-settling.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows[0],indent=2))
