#!/usr/bin/env python3
"""Reference motion near evaluations and limit of constant span-offset correction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence';rows=[]
for variant in ('reservoir','compensated','output2'):
 audit=json.loads((E/f'adc-reference-{variant}-decision-windows.json').read_text());W=R/f'scratch/transceiver-adc-sar8-reference-{variant}';allmeans=[];cases=[]
 for case in audit['cases']:
  p=W/(case['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==case['waveform_sha256']
  with p.open() as f:
   header=f.readline().lower().split();assert header[43:45]==['v(vh)','v(vl)']
  a=np.loadtxt(p,skiprows=1);assert np.isfinite(a).all();steps=[]
  for frame in case['frames']:
   for s in frame['steps']:
    lo,hi=s['window_ns'];w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];assert len(w)>1
    span=w[:,43]-w[:,44];mean=float(span.mean());allmeans.append(mean)
    steps.append(dict(hold_ns=frame['hold_ns'],bit=s['bit'],window_ns=[lo,hi],span_mean_v=mean,span_motion_mv=float(np.ptp(span)*1e3),span_endpoint_change_mv=float((span[-1]-span[0])*1e3),span_secant_mv_per_ns=float((span[-1]-span[0])/(w[-1,0]-w[0,0])*1e-6)))
  cases.append(dict(name=case['name'],steps=steps))
 lo=min(allmeans);hi=max(allmeans)
 rows.append(dict(variant=variant,cases=cases,decision_mean_span_range_v=[lo,hi],best_constant_additive_correction_v=1-(lo+hi)/2,minimum_worst_mean_span_error_after_constant_correction_mv=(hi-lo)*500,max_observed_in_window_span_motion_mv=max(s['span_motion_mv'] for c in cases for s in c['steps'])))
out=dict(status='reference_motion_and_constant_offset_limit',variants=rows,limitations=['Best constant correction is mathematical postprocessing of this finite record, not a circuit simulation or calibration implementation.', 'Changing physical target/bias can change dynamic behavior; this bound applies only to a fixed additive correction of measured span.', 'Endpoint secants and short-window motion do not prove ringing, stability or a specific failure mechanism.', 'No jitter/aperture integration, noise/mismatch or arbitrary-input qualification.'])
(E/'reference-motion-diagnostic.json').write_text(json.dumps(out,indent=2)+'\n')
for v in rows:print(v['variant'],v['decision_mean_span_range_v'],'constant-correction residual mV',v['minimum_worst_mean_span_error_after_constant_correction_mv'],'max window motion mV',v['max_observed_in_window_span_motion_mv'])
