#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-input-resistance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
assert len(r['cases'])==16
cell=(P/'analog/bb_filter_section.spice').read_text();half=cell.replace('RIP IP GP 1k','RIP IP GP 500').replace('RIN IN GN 1k','RIN IN GN 500').rstrip()
rows=[];seen=set()
for c in r['cases']:
 variant,kind,name=[c[x] for x in ('variant','kind','name')];key=(variant,kind,name);assert key not in seen;seen.add(key)
 work=W/variant/kind;base=R/'scratch'/('transceiver-bb-noise' if kind=='noise' else 'transceiver-bb-interface')
 assert c['returncode']==0 and sha(base/(name+'.spice'))==c['baseline_deck_sha256']
 assert len(c['artifacts_sha256'])==4
 for ext,h in c['artifacts_sha256'].items():assert sha(work/(name+ext))==h
 d=(work/(name+'.spice')).read_text().replace('/work/'+variant+'/'+kind+'/','/work/')
 if variant=='half':assert d.count(half)==1;d=d.replace(half,'.include /screen/bb_filter_section.spice')
 assert d==(base/(name+'.spice')).read_text()
 log=(work/(name+'.log')).read_text().lower();assert not any(x in log for x in ('error','aborted','unknown parameter'))
 def data(ext):
  a=np.loadtxt(work/(name+ext),skiprows=1);assert np.isfinite(a).all()
  if variant=='baseline':assert np.array_equal(a,np.loadtxt(base/(name+ext),skiprows=1))
  return a
 a=data('.dat');assert np.all(np.diff(a[:,0])>0)
 row=dict(variant=variant,kind=kind,name=name)
 if kind=='noise':
  assert a.shape==(201,3) and np.isclose(a[-1,0],1e8)
  data('-integrated.dat')
  f=a[:,0];x=np.r_[1e3,f[(f>1e3)&(f<20e6)],20e6]
  for i,label in ((1,'output'),(2,'input_referred')):
   row[label+'_rms_v_1k_20meg']=float(np.sqrt(np.trapezoid(np.interp(x,f,a[:,i]**2),x)))
 else:
  assert a.shape==(100,5) and np.isclose(a[-1,0],1e8)
  op=data('-op.dat')
  with (work/(name+'-op.dat')).open() as f:header=f.readline().lower().split()
  def v(n):return float(op[header.index(n)])
  assert len(op)==26
  row.update(output_common_mode_v=(v('v(op)')+v('v(on)'))/2,input_current_per_leg_a=-v('i(vip)'),power_w=-3.3*v('i(vdd)'),minimum_vds_margin_v=min(v(f'@m.xdut.{stage}.{dev}.m0[vds]')-v(f'@m.xdut.{stage}.{dev}.m0[vdsat]') for stage in ('xa','xb') for dev in ('xip','xin','xtail')))
  gain=np.hypot(a[:,1],a[:,2]);peak=int(np.argmax(gain))
  row.update(source_gain_1meg=float(gain[0]),source_gain_peak_1_to_100meg=float(gain[peak]),source_gain_peak_frequency_hz=float(a[peak,0]))
  k=np.flatnonzero(np.isclose(a[:,0],20e6));assert len(k)==1
  z=a[k[0]];row['source_gain_20meg']=float(abs(z[1]+1j*z[2]));row['port_gain_20meg']=float(abs((z[1]+1j*z[2])/(z[3]+1j*z[4])))
 rows.append(row)
comparisons=[]
for b in [x for x in rows if x['variant']=='baseline']:
 c=next(x for x in rows if x['variant']=='half' and x['kind']==b['kind'] and x['name']==b['name'])
 keys=('output_rms_v_1k_20meg','input_referred_rms_v_1k_20meg') if b['kind']=='noise' else ('source_gain_20meg','input_current_per_leg_a','power_w')
 comparisons.append(dict(kind=b['kind'],name=b['name'],candidate_over_baseline={k:c[k]/b[k] for k in keys}))
out=dict(completed=True,provenance=r,cases=rows,comparisons=comparisons,limitations=['Isolated stationary filter diagnostic; actual switched mixer integration and noise folding absent.','Positive DC margin and AC response do not establish loop stability, startup or large-signal behavior.','500ohm input resistor candidate not adopted by this checker; no system receiver noise qualification.'])
(P/'evidence/bb-input-resistance.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 if row['variant']=='half':print(row)
print(comparisons)
