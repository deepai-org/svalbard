"""Observed128->64 command with ideal versus actual drivers and real references."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-observed-sar-transition';W.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent=R/'scratch/transceiver-carry-rail-probes/code128_delay100.spice';priorpath=P/'evidence/carry-rail-probes.json';prior=json.loads(priorpath.read_text());case=next(c for c in prior['cases'] if c['name']=='code128_delay100');assert sha(parent)==case['artifacts_sha256']['.spice'];base=parent.read_text();cases=[]
for physical in [False,True]:
 name='physical' if physical else 'ideal';s=base;drivers=[]
 for k in range(8):
  start=3.3 if 128&(1<<k) else 0;other=3.3 if 64&(1<<k) else 0
  value=f'PWL(0 {start} 2n {start} 2.1n {other} 5n {other} 5.1n {start})'
  inverse=f'PWL(0 {3.3-start} 2n {3.3-start} 2.1n {3.3-other} 5n {3.3-other} 5.1n {3.3-start})'
  if physical:
   s,n=re.subn(rf'^VB{k} B{k} 0 .*$',f'VCMD{k} D{k} 0 {value}',s,flags=re.M);assert n==1
   s,n=re.subn(rf'^VBB{k} BB{k} 0 .*\n','',s,flags=re.M);assert n==1
   drivers.append(f'XDRV{k} D{k} B{k} BB{k} VDD 0 pt_adc_code_small_driver WEIGHT={2**k}')
  else:
   s,n=re.subn(rf'^VB{k} B{k} 0 .*$',f'VB{k} B{k} 0 {value}',s,flags=re.M);assert n==1
   s,n=re.subn(rf'^VBB{k} BB{k} 0 .*$',f'VBB{k} BB{k} 0 {inverse}',s,flags=re.M);assert n==1
 if physical:s=s.replace('.control','.include /screen/adc/code_driver_small.spice\n'+'\n'.join(drivers)+'\n.control')
 s=s.replace('/work/code128_delay100.dat',f'/work/{name}.dat').replace('i(VPROBEL)','i(VPROBEL) v(B6) v(BB6) v(B7) v(BB7)')
 (W/(name+'.spice')).write_text(s);cases.append(dict(name=name,physical_drivers=physical))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[R/p for p in prior['source_sha256']]+[P/'analog/adc/code_driver_small.spice'];hashes={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert hashes=={str(p.relative_to(R)):sha(p) for p in files}
for c in cases:
 name=c['name'];log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==15 and np.isfinite(a).all() and a[-1,0]>=8e-9;t=a[:,0];mask=(t>=2e-9)&(t<=4.4e-9)
 tt=np.r_[2e-9,t[(t>2e-9)&(t<4.4e-9)],4.4e-9]
 c.update(reference_span_range_v=[float(min(a[mask,6]-a[mask,7])),float(max(a[mask,6]-a[mask,7]))],net_high_charge_c=float(np.trapezoid(np.interp(tt,t,a[:,9]),tt)),net_low_charge_c=float(np.trapezoid(np.interp(tt,t,a[:,10]),tt)),settled_differential_v=float(np.interp(4.4e-9,t,a[:,1]-a[:,2])),artifacts_sha256={e:sha(W/(name+e)) for e in ['.spice','.log','.dat']})
report=dict(status='observed_transition_driver_comparison',source_sha256=hashes,image=image,parent_sha256=sha(parent),cases=cases,limitations=['Observed command pair only; command waveform and isolated history are synthetic, not closed SAR replay.', 'Reference biases/supply and external command edges remain ideal; comparator held reset.', 'Signed load probes retained, but prior reproduction scope was a different transition.', 'One direction, nominal process; not complete conversion or throughput qualification.'])
(P/'evidence/observed-sar-transition.json').write_text(json.dumps(report,indent=2)+'\n');print([(c['name'],c['reference_span_range_v'],c['net_high_charge_c'],c['net_low_charge_c']) for c in cases])
