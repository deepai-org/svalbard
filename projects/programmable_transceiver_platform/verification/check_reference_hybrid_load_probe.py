"""Verify observation-only replay and report high-load transistor state."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-hybrid-load-probe';B=R/'scratch/transceiver-reference-hybrid-load-tolerance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());b=json.loads((B/'result.json').read_text());rows=[]
for c in r['cases']:
 name=c['name'];old=next(x for x in b['cases'] if x['name']==name)
 for root,case in ((W,c),(B,old)):
  assert case['returncode']==0 and case['sources_before']==case['sources_after']
  for ext,h in case['artifacts_sha256'].items():assert sha(root/(name+ext))==h
  assert not any(k in (root/(name+'.log')).read_text().lower() for k in ('error','warning','aborted'))
 d=(W/(name+'.spice')).read_text();base=(B/(name+'.spice')).read_text();lines=d.splitlines();save=next(l for l in lines if l.startswith('save all '));wr=next(l for l in lines if l.startswith('wrdata '));oldwr=next(l for l in base.splitlines() if l.startswith('wrdata '));assert d.replace(save+'\n','').replace(wr,oldwr)==base
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);original=np.loadtxt(B/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and np.array_equal(a[:,:5],original)
 with (W/(name+'.dat')).open() as stream:h=stream.readline().lower().split()
 assert len(h)==a.shape[1];samples=[]
 for current in (-.005,0,.005,.01):
  i=int(abs(a[:,0]-current).argmin());assert abs(a[i,0]-current)<1e-15
  devices={}
  for dev in ('xip','xin','xt','xmp','xmn','xout','xload'):
   values={q:float(a[i,h.index(f'@m.xdut.xhigh.{dev}.m0[{q}]')]) for q in ('vds','vdsat','id','gm','gds')}
   values['reported_margin_v']=abs(values['vds'])-abs(values['vdsat']);devices[dev]=values
  samples.append(dict(load_a=current,high_v=float(a[i,1]),output_gate_v=float(a[i,3]),tail_v=float(a[i,h.index('v(xdut.xhigh.t)')]),devices=devices))
 rows.append(dict(name=name,original_vectors_bit_identical=True,artifacts_sha256=c['artifacts_sha256'],samples=samples))
out=dict(completed=True,cases=rows,limitations=['Reported model margins are diagnostic and do not uniquely establish causation or stability.', 'Static loaded sweep, not time-varying ADC demand; device sizing needs dynamic and power checks.'])
(P/'evidence/reference-hybrid-load-probe.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 if row['name'].endswith('up'):
  for x in row['samples']:print(row['name'],x['load_a'],'gate',x['output_gate_v'],'margins', {k:round(v['reported_margin_v'],6) for k,v in x['devices'].items()})
