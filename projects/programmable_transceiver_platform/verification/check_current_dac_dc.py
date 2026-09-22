#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-current-dc'
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];assert {c['output_clamp_v'] for c in r['cases']}=={1.2,1.65,2.1}
source=P/'analog/dac/current_steering8.spice';assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256_before']['/screen/dac/current_steering8.spice']
s=source.read_text()
for bit in range(8):assert f'X{bit} OP ON B{bit} B{bit}B BN VSS pt_dac_current_bit WGT={2**bit}' in s
assert 'XTAIL T BN VSS VSS nfet_03v3 w=10u l=1u m={WGT}' in s
for c in r['cases']:
 name=c['name'];assert c['returncode']==0
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(256,21) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
 header=(W/(name+'.dat')).read_text().splitlines()[0].split();assert header[1:4]==['i(VOP)','i(VON)','v(BN)']
 for bit in range(8):
  assert header[4+2*bit:6+2*bit]==[f'v(B{bit})',f'v(B{bit}B)']
  expected=((np.arange(256)>>bit)&1)*3.3
  assert np.allclose(a[:,4+2*bit],expected,atol=1e-9) and np.allclose(a[:,5+2*bit],3.3-expected,atol=1e-9)
 current=a[:,2]-a[:,1];total=-a[:,1]-a[:,2];lsb=(current[-1]-current[0])/255;steps=np.diff(current)
 c.update(differential_endpoints_ma=[float(current[0]*1e3),float(current[-1]*1e3)],endpoint_lsb_ua=float(lsb*1e6),strictly_monotonic=bool(np.all(steps>0)),max_endpoint_normalized_dnl_lsb=float(np.max(abs(steps/lsb-1))),max_endpoint_normalized_inl_lsb=float(np.max(abs((current-(current[0]+np.arange(256)*lsb))/lsb))),total_output_current_range_ma=[float(total.min()*1e3),float(total.max()*1e3)],bias_range_v=[float(a[:,3].min()),float(a[:,3].max())])
r['status']='matched_static_current_DAC_transfer_audited';r['qualified_radio_DAC']=False
r['limitations'].append('Tiny normalized static errors in matched weighted instances do not establish physical eight-bit precision or dynamic ENOB.')
(P/'evidence/current-dac-dc-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('name','differential_endpoints_ma','endpoint_lsb_ua','strictly_monotonic','max_endpoint_normalized_dnl_lsb','total_output_current_range_ma')} for c in r['cases']],indent=2))
assert all(c['strictly_monotonic'] for c in r['cases'])
