"""Windowed dynamic errors referenced to each circuit's own measured DC transfer."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-large-input-step';n='cm1.177_fb20000'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert len(r['cases'])==2;rows=[]
for c in r['cases']:
 label=c['name'];B=R/'scratch'/('transceiver-bb-feedback-swing' if label=='baseline' else 'transceiver-bb-large-input-swing')
 assert c['returncode']==0 and c['sources_before']==c['sources_after'] and sha(B/(n+'.spice'))==c['parent_sha256']
 br=json.loads((B/'result.json').read_text());bc=next(x for x in br['cases'] if x['name']==n)
 assert sha(B/(n+'.dat'))==bc['artifacts_sha256']['.dat']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(label+ext))==h
 d=(W/(label+'.spice')).read_text();assert d.replace(r['pulse'],'VD D 0 0').replace('tran 20p 300n 0 20p','dc VD -.4 .4 .005').replace(f'/work/{label}.dat',f'/work/{n}.dat')==(B/(n+'.spice')).read_text()
 log=(W/(label+'.log')).read_text().lower();assert not any(x in log for x in ('warning','error','aborted'))
 with (W/(label+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(label+'.dat'),skiprows=1);t=a[:,0];assert len(h)==a.shape[1] and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=300e-9
 with (B/(n+'.dat')).open() as f:bh=f.readline().lower().split()
 b=np.loadtxt(B/(n+'.dat'),skiprows=1);by=b[:,bh.index('v(op)')]-b[:,bh.index('v(on)')]
 y=a[:,h.index('v(op)')]-a[:,h.index('v(on)')];events=[]
 for edge,target,end in [(20,.05,119),(120,-.05,219),(220,0,299)]:
  k=int(abs(b[:,0]-target).argmin());assert abs(b[k,0]-target)<1e-12;dc=float(by[k]);mask=(t>=(edge+.1)*1e-9)&(t<=end*1e-9);windows=[]
  for lo,hi in [(edge+40,edge+50),(edge+60,edge+70)]:
   m=(t>=lo*1e-9)&(t<=hi*1e-9);assert m.any();windows.append(dict(window_ns=[lo,hi],max_dc_error_v=float(abs(y[m]-dc).max())))
  events.append(dict(edge_ns=edge,source_target_v=target,dc_target_v=dc,response_min_v=float(y[mask].min()),response_max_v=float(y[mask].max()),windows=windows))
 rows.append(dict(case=label,events=events,artifacts_sha256=c['artifacts_sha256']))
out=dict(completed=True,cases=rows,limitations=['Selected zero/positive/negative steps with1kohm source legs only; no actual mixer or ADC loading.','Errors relative to circuit-specific DC target isolate dynamics, not overall gain accuracy.','No allocated settling threshold, return-ratio stability margin, noise or PVT qualification.'])
(P/'evidence/bb-large-input-step.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
