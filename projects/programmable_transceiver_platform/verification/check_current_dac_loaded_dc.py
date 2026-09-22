#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-loaded-dc';B=R/'scratch/transceiver-dac-current-dc'
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];assert {(c['termination_v'],c['resistance_ohm']) for c in r['cases']}=={(v,res) for v in (2.15,3.3) for res in (50,100,200,400)}
source=P/'analog/dac/current_steering8.spice';assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256_before']['/screen/dac/current_steering8.spice']
original=B/'cm1.65.spice';assert hashlib.sha256(original.read_bytes()).hexdigest()==r['baseline_deck_sha256']
for c in r['cases']:
 name=c['name'];term=c['termination_v'];res=c['resistance_ohm'];assert c['returncode']==0
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text().replace(f'VTERM TERM 0 {term}\nRP TERM OP {res}\nRN TERM ON {res}\n','VOP OP 0 1.65\nVON ON 0 1.65\n').replace(f'/work/{name}.dat','/work/cm1.65.dat').replace('v(OP) v(ON)','i(VOP) i(VON)');assert d==original.read_text()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(256,21) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
 header=(W/(name+'.dat')).read_text().splitlines()[0].split();assert header[1:4]==['v(OP)','v(ON)','v(BN)']
 for bit in range(8):
  expected=((np.arange(256)>>bit)&1)*3.3
  assert np.allclose(a[:,4+2*bit],expected,atol=1e-9) and np.allclose(a[:,5+2*bit],3.3-expected,atol=1e-9)
 v=a[:,2]-a[:,1];lsb=(v[-1]-v[0])/255;steps=np.diff(v);current=(2*term-a[:,1]-a[:,2])/res
 c.update(differential_endpoints_v=[float(v[0]),float(v[-1])],endpoint_lsb_mv=float(lsb*1e3),strictly_monotonic=bool(np.all(steps>0)),max_endpoint_normalized_inl_lsb=float(np.max(abs((v-(v[0]+np.arange(256)*lsb))/lsb))),max_endpoint_normalized_dnl_lsb=float(np.max(abs(steps/lsb-1))),output_range_v=[float(a[:,1:3].min()),float(a[:,1:3].max())],total_current_range_ma=[float(current.min()*1e3),float(current.max()*1e3)],common_mode_range_v=[float(np.mean(a[:,1:3],axis=1).min()),float(np.mean(a[:,1:3],axis=1).max())])
r['status']='finite_load_current_DAC_transfer_audited';r['qualified_radio_DAC']=False
(P/'evidence/current-dac-loaded-dc-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('name','differential_endpoints_v','max_endpoint_normalized_inl_lsb','max_endpoint_normalized_dnl_lsb','strictly_monotonic','output_range_v')} for c in r['cases']],indent=2))
