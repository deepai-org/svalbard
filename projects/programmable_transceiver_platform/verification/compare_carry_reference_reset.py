"""Matched comparator-clock isolation; verify sole deck mutation and waveforms."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
paths=[P/'evidence'/('cdac-carry-real-reference'+suffix+'.json') for suffix in ['', '-reset']]
a,b=[json.loads(p.read_text()) for p in paths];rows=[]
for ca,cb in zip(a['cases'],b['cases'],strict=True):
 assert ca['name']==cb['name'];name=ca['name'];wa=R/'scratch/transceiver-cdac-carry-real-reference';wb=R/'scratch/transceiver-cdac-carry-real-reference-reset'
 sa=(wa/(name+'.spice')).read_text();sb=(wb/(name+'.spice')).read_text()
 assert re.sub(r'^VC CLK 0 .*$', 'VC CLK 0 0',sa,flags=re.M)==sb
 for folder,case in [(wa,ca),(wb,cb)]:
  for ext,h in case['artifacts_sha256'].items():assert hashlib.sha256((folder/(name+ext)).read_bytes()).hexdigest()==h
 x=np.loadtxt(wa/(name+'.dat'),skiprows=1);y=np.loadtxt(wb/(name+'.dat'),skiprows=1)
 tt=np.unique(np.r_[2e-9,x[(x[:,0]>2e-9)&(x[:,0]<4.4e-9),0],y[(y[:,0]>2e-9)&(y[:,0]<4.4e-9),0],4.4e-9])
 sx=np.interp(tt,x[:,0],x[:,6]-x[:,7]);sy=np.interp(tt,y[:,0],y[:,6]-y[:,7]);delta=sx-sy
 rows.append(dict(name=name,clocked_minimum_span_v=float(min(sx)),reset_minimum_span_v=float(min(sy)),maximum_clocked_minus_reset_span_v=float(max(abs(delta))),preclock_maximum_difference_v=float(max(abs(delta[tt<=2.2e-9])))))
report=dict(status='matched_reset_isolation_complete',sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},cases=rows,limitations=['Clock removal isolates its contribution in this fixture; does not distinguish CDAC redistribution from switch overlap/injection.', 'Ideal sources and prebiased nominal single-CDAC case remain.', 'Correct-target-polarity field in reset-run raw report is inapplicable because comparator is intentionally never evaluated.'])
(P/'evidence/cdac-carry-reset-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)
