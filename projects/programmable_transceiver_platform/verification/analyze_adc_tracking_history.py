#!/usr/bin/env python3
"""Measure loaded acquisition history; no stability or causal attribution claim."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--fixed-references",action="store_true");ap.add_argument("--damping",action="store_true");ap.add_argument("--two-k",action="store_true");args=ap.parse_args()
assert sum((args.damping,args.fixed_references,args.two_k))<=1
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3]
P=R/'projects/programmable_transceiver_platform'
rows=[]; hashes={}
for case in (('receiver-cm','damping','damping2k') if args.two_k else ('receiver-cm','damping') if args.damping else ('receiver-cm','fixed-references') if args.fixed_references else ('receiver-cm','compensation')):
 w=R/('scratch/transceiver-adc-shared-iq-'+case)
 result=json.loads((w/'result.json').read_text())
 assert result['returncode']==0 and not result['timed_out']
 for ext,digest in result['artifacts_sha256'].items():
  assert hashlib.sha256((w/('frames'+ext)).read_bytes()).hexdigest()==digest
 hashes[case]=result['artifacts_sha256']
 with (w/'frames.dat').open() as f: header=f.readline().lower().split()
 a=np.loadtxt(w/'frames.dat',skiprows=1)
 assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0) and a[-1,0]+1e-21>=209.9e-9
 for start in (60,110,160):
  target=.4 if start==110 else -.4
  b=a[(a[:,0]>=(start+.1)*1e-9)&(a[:,0]<=(start+9.9)*1e-9)]
  def v(name):return b[:,header.index('v('+name+')')]
  signals={'driver':v('ip')-v('in'),'plate':v('hp')-v('hn'),'msb_bottom':v('xd.xp7.bot')-v('xd.xn7.bot')}
  measures={}
  for name,y in signals.items():
   measures[name]={'range_v':[float(y.min()),float(y.max())]}
   if name!='msb_bottom':
    signed=(y-target)*np.sign(target); k=int(np.argmax(signed))
    measures[name].update(overshoot_beyond_target_v=float(signed[k]),overshoot_time_ns=float(b[k,0]*1e9))
  samples=[]
  for offset in (2,4,6,8,9,9.8):
   k=int(np.argmin(abs(b[:,0]-(start+offset)*1e-9)))
   samples.append(dict(actual_time_ns=float(b[k,0]*1e9),**{name:float(y[k]) for name,y in signals.items()}))
  controls={n:[float(v(n).min()),float(v(n).max())] for n in ['sd'+str(i) for i in range(8)]+['b7','b7b']}
  rows.append(dict(case=case,step_ns=start,target_v=target,measurements=measures,tracking_control_ranges_v=controls,samples=samples))
out=dict(status='completed_saved_waveform_diagnostic',cases=rows,artifacts_sha256=hashes,limitations=['Ideal sampling clocks and source drive remain.','Only MSB physical bottom plates saved; not all capacitor branch currents.','Overshoot during tracking does not establish loop stability or isolate its cause.','Sparse samples supplement whole-window extrema; they are not settling qualification.'])
(P/('evidence/adc-tracking-history-damping2k.json' if args.two_k else 'evidence/adc-tracking-history-damping.json' if args.damping else 'evidence/adc-tracking-history-fixed-references.json' if args.fixed_references else 'evidence/adc-tracking-history.json')).write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['case'],row['step_ns'],row['measurements'])
