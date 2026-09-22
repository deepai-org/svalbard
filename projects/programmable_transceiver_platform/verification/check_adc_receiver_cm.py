#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-receiver-cm'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];assert sorted(c['load_ua'] for c in r['cases'])==[-100,0,100];rows=[];sweeps=[]
for c in r['cases']:
 assert c['returncode']==0
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
 assert set(c['artifacts_sha256'])=={'.spice','.log','.dat'}
 assert 'aborted' not in (W/(c['name']+'.log')).read_text().lower()
 with (W/(c['name']+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert a.shape==(101,len(h)) and np.isfinite(a).all();np.testing.assert_allclose(a[:,0],np.linspace(.85,1.85,101),atol=1e-12,rtol=0)
 headroom=a[:,h.index('@m.xbuf.xt.m0[vds]')]-a[:,h.index('@m.xbuf.xt.m0[vdsat]')]
 k=np.flatnonzero((headroom[:-1]<0)&(headroom[1:]>=0));brackets=[[float(a[i,0]),float(a[i+1,0])] for i in k]
 gain=np.diff(a[:,h.index('v(out)')])/np.diff(a[:,0]);region=(a[:-1,0]>=.95-1e-12)&(a[1:,0]<=1.15+1e-12)
 sweeps.append(dict(load_ua=c['load_ua'],tail_model_saturation_crossing_brackets_v=brackets,local_secant_gain_095_to_115_v=[float(gain[region].min()),float(gain[region].max())],tracking_error_095_to_115_v=[float((a[(a[:,0]>=.95-1e-12)&(a[:,0]<=1.15+1e-12),h.index('v(out)')]-a[(a[:,0]>=.95-1e-12)&(a[:,0]<=1.15+1e-12),0]).min()),float((a[(a[:,0]>=.95-1e-12)&(a[:,0]<=1.15+1e-12),h.index('v(out)')]-a[(a[:,0]>=.95-1e-12)&(a[:,0]<=1.15+1e-12),0]).max())]))
 for target in (1.07,1.65):
  k=int(np.argmin(abs(a[:,0]-target)));assert abs(a[k,0]-target)<1e-12
  def v(n):return float(a[k,h.index(n)])
  rows.append(dict(load_ua=c['load_ua'],target_v=target,output_v=v('v(out)'),error_v=v('v(out)')-target,supply_power_w=-3.3*v('i(vdd)'),device_model_headroom_v={x:v(f'@m.xbuf.{x}.m0[vds]')-v(f'@m.xbuf.{x}.m0[vdsat]') for x in ('xt','xip','xin','xout','xload')}))
out=dict(status='completed_DC_diagnostic',rows=rows,sweep_diagnostics=sweeps,provenance=r,limitations=['Ideal input/bias/supply; constant loads are diagnostics, not CDAC current bounds.','No filter loading dynamics, switched settling, stability, noise or ADC accuracy qualification.','VDS-VDSAT uses model convention; sign alone is not qualification.'])
(P/'evidence/adc-receiver-cm.json').write_text(json.dumps(out,indent=2)+'\n')
for row in sweeps:print(row)
