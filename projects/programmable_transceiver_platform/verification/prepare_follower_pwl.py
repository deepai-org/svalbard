#!/usr/bin/env python3
"""Replace only ideal reference representation; retain actual autonomous loop."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-closed-loop-follower';O=R/'scratch/transceiver-closed-loop-follower-pwl-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text())
assert r['source_sha256_before']==r['source_sha256_after'] and r['deck_unchanged']
assert sha(B/'closed.spice')==r['artifacts_sha256']['.spice']
base=(B/'closed.spice').read_text()
old='VREF REFRAW 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
assert base.count(old)==1
# Integer picoseconds avoid accumulated decimal timing errors.
points=[(0,0)]
for k in range(62):
 t=100000+k*51200
 points.extend([(t,0),(t+100,3.3),(t+25600,3.3),(t+25700,0)])
assert points[-1][0]>3201000
new='VREF REFRAW 0 PWL('+' '.join(f'{t}p {v}' for t,v in points)+')'
d=base.replace(old,new);assert d.replace(new,old)==base
# Verify all breakpoints and adjacent midpoints against independent pulse formula.
x=np.array([p[0] for p in points],dtype=float);y=np.array([p[1] for p in points])
test=np.unique(np.r_[x,(x[:-1]+x[1:])/2]);test=test[test<=3201000]
def pulse(t):
 if t<100000:return 0.
 phase=(t-100000)%51200
 if phase<100:return 3.3*phase/100
 if phase<=25600:return 3.3
 if phase<25700:return 3.3*(25700-phase)/100
 return 0.
error=max(abs(np.interp(t,x,y)-pulse(t)) for t in test)
assert error<1e-12
O.mkdir(exist_ok=True);(O/'closed.spice').write_text(d)
m=dict(prepared_deck_sha256=sha(O/'closed.spice'),baseline_deck_sha256=sha(B/'closed.spice'),exact_substitution_reversal_verified=True,old_source=old,new_source=new,comparison_points=len(test),max_ideal_waveform_error_v=error,scope='Only PULSE-to-explicit-PWL reference representation; same intended edges, actual divider feedback and transistor circuit retained.',limitations=['Mathematical equivalence is not proof of identical numerical stepping.','This is a solver discriminator, not a physical circuit repair.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(P/'evidence/follower-pwl-preparation.json').write_text(json.dumps(m,indent=2)+'\n')
print('exact reversal; waveform checks',len(test),'error',error)
