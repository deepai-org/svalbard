"""Single-device strength comparison, static diagnostic only."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-hybrid-output2-dc';B=R/'scratch/transceiver-reference-hybrid-load-probe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());b=json.loads((B/'result.json').read_text());rows=[];arrays={}
old='XOUT OUT X VDD VDD pfet_03v3 w=8u l=.5u m={8*S}';new=old.replace('m={8*S}','m={16*S}')
for c in r['cases']:
 name=c['name'];bc=next(x for x in b['cases'] if x['name']==name)
 for root,case in ((W,c),(B,bc)):
  assert case['returncode']==0 and case['sources_before']==case['sources_after']
  for ext,h in case['artifacts_sha256'].items():assert sha(root/(name+ext))==h
  assert not any(k in (root/(name+'.log')).read_text().lower() for k in ('error','warning','aborted'))
 d=(W/(name+'.spice')).read_text();assert d.count(new)==1 and d.replace(new,old)==(B/(name+'.spice')).read_text()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);base=np.loadtxt(B/(name+'.dat'),skiprows=1)
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 with (B/(name+'.dat')).open() as f:assert h==f.readline().lower().split()
 assert a.shape==base.shape==(81,len(h)) and np.isfinite(a).all() and np.array_equal(a[:,0],base[:,0])
 arrays[name]=a if name.endswith('up') else a[::-1];samples=[]
 for load in (-.01,-.005,0,.005,.01):
  i=int(abs(a[:,0]-load).argmin());assert abs(a[i,0]-load)<1e-15
  pairs=[]
  for label,x in [('parent_hybrid',base),('output2',a)]:
   def v(n):return float(x[i,h.index(n)])
   pairs.append(dict(case=label,high_v=v('v(oh)'),gate_v=v('v(xdut.xhigh.x)'),xin_reported_margin_v=abs(v('@m.xdut.xhigh.xin.m0[vds]'))-abs(v('@m.xdut.xhigh.xin.m0[vdsat]')),power_w=-3.3*v('i(vdd)')))
  samples.append(dict(load_a=load,values=pairs))
 rows.append(dict(name=name,artifacts_sha256=c['artifacts_sha256'],samples=samples))
out=dict(completed=True,cases=rows,direction_max_high_difference_v=float(abs(arrays['hybrid_up'][:,1]-arrays['hybrid_down'][:,1]).max()),limitations=['Only output PMOS multiplicity doubles; high input topology remains experimental.', 'No dynamic stability, pulse regulation, switched ADC performance, noise or physical area qualification.', 'Reverse-load rail excursion remains failed; no candidate promotion.'])
(P/'evidence/reference-hybrid-output2-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows[0]['samples'],indent=2));print('direction',out['direction_max_high_difference_v'])
