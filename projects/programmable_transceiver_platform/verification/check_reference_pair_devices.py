#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-pair-device-dc';B=R/'scratch/transceiver-reference-pair-target-dc-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());br=json.loads((B/'result.json').read_text());rows=[]
assert r['sources_before']==r['sources_after']
for c in r['cases']:
 n=c['name'];bc=next(x for x in br['cases'] if x['name']==n)
 for root,record in [(W,c),(B,bc)]:
  assert record['returncode']==0
  for ext,h in record['artifacts_sha256'].items():assert sha(root/(n+ext))==h
  log=(root/(n+'.log')).read_text().lower();assert not any(x in log for x in ['error','warning','aborted'])
 with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
 with (B/(n+'.dat')).open() as f:bh=f.readline().lower().split()
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);b=np.loadtxt(B/(n+'.dat'),skiprows=1)
 assert a.shape==(41,len(h)) and np.isfinite(a).all() and h[:len(bh)]==bh
 identical=np.array_equal(a[:,:len(bh)],b);assert identical
 v=dict(zip(h,a[20]));stages=[]
 for stage in ('xhigh','xlow'):
  devices=[]
  for dev in ('xip','xin','xt','xmp','xmn','xout','xload'):
   stem=f'@m.xdut.{stage}.{dev}.m0';values={q:float(v[stem+f'[{q}]']) for q in ('vds','vdsat','id','gm','gds')}
   devices.append(dict(device=dev,**values,reported_margin_v=values['vds']-values['vdsat']))
  stages.append(dict(stage=stage,internal_nodes_v={node:float(v[f'v(xdut.{stage}.{node})']) for node in ('a','x','t')},devices=devices))
 rows.append(dict(case=n,original_vectors_identical=identical,stages=stages))
out=dict(completed=True,provenance=r,cases=rows,limitations=['Model-reported currents and margins require orientation/physical-terminal checks before causal interpretation.','Zero-load DC nominal targets; no dynamic regulation, noise or process qualification.','Device correlations alone do not establish cause of offset.'])
(P/'evidence/reference-pair-devices.json').write_text(json.dumps(out,indent=2)+'\n')
for s in rows[0]['stages']:print(s['stage'],[(x['device'],round(x['reported_margin_v'],5),round(x['id']*1e6,3)) for x in s['devices']])
