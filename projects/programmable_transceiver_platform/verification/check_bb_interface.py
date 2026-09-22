#!/usr/bin/env python3
import hashlib,itertools,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-interface'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
assert [(c['common_mode_v'],c['source_ohm_per_leg']) for c in r['cases']]==list(itertools.product([.6,.9,1.177],[0,1000]))
rows=[]
for c in r['cases']:
 name=c['name'];assert c['returncode']==0 and 'aborted' not in (W/(name+'.log')).read_text().lower()
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
 with (W/(name+'-op.dat')).open() as f:assert f.readline().lower().split()[1:]==[x.lower() for x in m['op_probes']]
 a=np.loadtxt(W/(name+'-op.dat'),skiprows=1);assert a.shape==(26,) and np.isfinite(a).all();v=dict(zip(m['op_probes'],a[1:]))
 with (W/(name+'.dat')).open() as f:assert f.readline().lower().split()==['frequency','gr','gi','ir','ii']
 ac=np.loadtxt(W/(name+'.dat'),skiprows=1);assert ac.shape==(100,5) and np.isfinite(ac).all() and np.allclose(ac[:,0],np.arange(1,101)*1e6,rtol=1e-12,atol=0)
 g=ac[:,1]+1j*ac[:,2];inp=ac[:,3]+1j*ac[:,4]
 devices=[]
 for stage in ('xa','xb'):
  for dev in ('xip','xin','xtail'):
   vd=float(v[f'@m.xdut.{stage}.{dev}.m0[vds]']);vs=float(v[f'@m.xdut.{stage}.{dev}.m0[vdsat]']);devices.append(dict(device=stage+'.'+dev,reported_vds_v=vd,reported_margin_v=vd-vs))
 rows.append(dict(common_mode_v=c['common_mode_v'],source_ohm_per_leg=c['source_ohm_per_leg'],input_v=[float(v['v(IP)']),float(v['v(IN)'])],output_v=[float(v['v(OP)']),float(v['v(ON)'])],current_into_inputs_a=[float(-v['i(VIP)']),float(-v['i(VIN)'])],supply_power_w=float(-3.3*v['i(VDD)']),devices=devices,ac=[dict(frequency_hz=float(ac[k-1,0]),source_to_output_gain=float(abs(g[k-1])),port_to_output_gain=float(abs(g[k-1]/inp[k-1])),input_differential_fraction=float(abs(inp[k-1]))) for k in (1,10,20,30)]))
out=dict(completed=True,provenance=r,cases=rows,limitations=['DC and small-signal AC only; neither stability nor startup nor connected mixer/filter quality proved.','Ideal bias/supply/source and lumped filter passives; no noise/mismatch/process or ADC loading qualification.','Signed source currents describe DC loading; device margins use model-reported convention.'])
(P/'evidence/bb-interface.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['common_mode_v'],x['source_ohm_per_leg'],'input/output',x['input_v'],x['output_v'],'input currents',x['current_into_inputs_a'],'worstmargin',min(d['reported_margin_v'] for d in x['devices']),'g20',x['ac'][2])
