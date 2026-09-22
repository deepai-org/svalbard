"""Test adequacy of a one-state reference model; do not promote a poor fit."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];source=P/'evidence/sar-physical-divergence.json'
d=json.loads(source.read_text())
assert d['source_sha256']==hashlib.sha256((P/'evidence/sar-driver-physical.json').read_bytes()).hexdigest()
training=[r for r in d['results'] if r['case']=='sar-driver-physical-400']
testing=[r for r in d['results'] if r['case']=='sar-driver-physical-100']
def features(error,previous,current):
    return [error,(previous^current)/256,(current-previous)/256,1.]
x=[];y=[]
for row in training:
    for prev,cur in zip(row['steps'],row['steps'][1:]):
        x.append(features(prev['reference_span_v']-1,prev['actual_trial'],cur['actual_trial']))
        y.append(cur['reference_span_v']-1)
x=np.asarray(x);y=np.asarray(y)
coef,_,rank,_=np.linalg.lstsq(x,y,rcond=None);assert rank==4
rows=[]
for row in training+testing:
    s=row['steps'];error=s[0]['reference_span_v']-1;predicted=[error+1]
    for previous,current in zip(s,s[1:]):
        error=float(np.dot(features(error,previous['actual_trial'],current['actual_trial']),coef))
        predicted.append(1+error)
    actual=np.array([v['reference_span_v'] for v in s]);difference=np.asarray(predicted)-actual
    rows.append(dict(case=row['case'],hold_ns=row['hold_ns'],training=row in training,
        predicted_span_v=predicted,actual_span_v=actual.tolist(),
        maximum_span_error_v=float(max(abs(difference))),rms_span_error_v=float(np.sqrt(np.mean(difference**2)))))
out=dict(coefficients=dict(zip(['previous_span_error','switched_weight','signed_code_step','constant'],map(float,coef))),
    stable_unforced_pole=bool(abs(coef[0])<1),training_condition=float(np.linalg.cond(x)),
    training_one_step_rms_v=float(np.sqrt(np.mean((x@coef-y)**2))),results=rows,
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Starts each frame from measured reference span and uses observed code histories.',
      'Rollout does not receive intermediate measured spans; this is still not closed-loop conversion prediction.',
      'Single span state omits separate rails, amplifier internal state and within-bit settling.',
      'Three training and three test frames are insufficient for universal identification.'])
(P/'evidence/sar-reference-recurrence-screen.json').write_text(json.dumps(out,indent=2)+'\n')
print(out['coefficients'], 'stable',out['stable_unforced_pole'])
for row in rows:print(row['case'],row['hold_ns'],row['maximum_span_error_v'])
