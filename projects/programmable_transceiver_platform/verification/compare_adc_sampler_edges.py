#!/usr/bin/env python3
"""Compare physical hold-edge perturbations at unchanged predecision windows."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[];hashes={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for case,offset in [('damping2k',0),('edge-early',-.1),('edge-late',.1)]:
 e=P/('evidence/adc-shared-iq-'+case+'.json');d=json.loads(e.read_text());assert d['completed'] and len(d['frames'])==3
 w=R/('scratch/transceiver-adc-shared-iq-'+case)
 for ext,h in d['provenance']['artifacts_sha256'].items():assert sha(w/('frames'+ext))==h
 hashes[case]=dict(evidence_sha256=sha(e),artifacts_sha256=d['provenance']['artifacts_sha256'])
 with (w/'frames.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(w/'frames.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 for f in d['frames']:
  hold=f['hold_ns'];target=.4 if hold==120 else -.4;win=a[(a[:,0]>=(hold+.2)*1e-9)&(a[:,0]<=(hold+.35)*1e-9)];t=win[:,0];assert len(t)>2
  for label,prefix in [('I',''),('Q','q_')]:
   y=win[:,h.index('v('+prefix+'hp)')]-win[:,h.index('v('+prefix+'hn)')];mean=float(np.trapezoid(y,t)/(t[-1]-t[0]))
   rows.append(dict(case=case,offset_ns=offset,hold_ns=hold,channel=label,held_mean_v=mean,error_v=mean-target,held_motion_v=float(np.ptp(y)),codes=f['channels'][label]['captured_codes']))
nom={(r['hold_ns'],r['channel']):r['held_mean_v'] for r in rows if r['case']=='damping2k'}
for r in rows:r['change_from_nominal_v']=r['held_mean_v']-nom[(r['hold_ns'],r['channel'])]
out=dict(status='completed_paired_sampler_edge_diagnostic',cases=rows,provenance=hashes,limitations=['Only selected +/-100ps simultaneous complementary release shifts; not arbitrary skew, jitter, PVT or source/load bounds.','Fixed predecision windows follow unchanged comparator schedule; actual mask/sampler interaction is retained.','Actual reference regulation still unqualified; correct codes do not establish transfer accuracy.'])
(P/'evidence/adc-sampler-edge-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
 if r['channel']=='I':print(r['case'],r['hold_ns'],'error_mV',r['error_v']*1e3,'delta_mV',r['change_from_nominal_v']*1e3,'codes',r['codes'])
