"""Matched actual-CDAC carry/reverse transitions with ideal gate commands/rails."""
import hashlib,json,subprocess,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-cdac-carry-transition';W.mkdir()
basepath=R/'scratch/transceiver-adc-cdac-kickback/d0.001_clk0.spice'
prior=json.loads((P/'evidence/adc-cdac-kickback.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
case=next(c for c in prior['cases'] if c['name']=='d0.001_clk0')
assert sha(basepath)==case['artifacts_sha256']['.spice'];base=basepath.read_text();cases=[]
for initial in [127,128]:
 for switching in [False,True]:
  name=f'code{initial}_switch{int(switching)}';s=base
  for k in range(8):
   high=3.3 if initial&(1<<k) else 0;low=3.3-high
   for prefix,node,start,other in [('VB',f'B{k}',high,low),('VBB',f'BB{k}',low,high)]:
    value=f'PWL(0 {start} 2n {start} 2.1n {other} 5n {other} 5.1n {start})' if switching else str(start)
    s,count=re.subn(rf'^{prefix}{k} {node} 0 .*$',f'{prefix}{k} {node} 0 {value}',s,flags=re.M);assert count==1
  s=s.replace('/work/d0.001_clk0.dat',f'/work/{name}.dat');(W/(name+'.spice')).write_text(s)
  cases.append(dict(name=name,initial_code=initial,switching=switching))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[P/'analog/adc/comparator.spice',P/'analog/adc/cdac8_mim.spice',P/'analog/adc/cdac8_scaled.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice'];hashes={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert hashes=={str(p.relative_to(R)):sha(p) for p in files}
arrays={}
for c in cases:
 name=c['name'];log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a[-1,0]>=8e-9;arrays[name]=a
 c['artifacts_sha256']={e:sha(W/(name+e)) for e in ['.spice','.log','.dat']}
rows=[]
for initial in [127,128]:
 a=arrays[f'code{initial}_switch1'];b=arrays[f'code{initial}_switch0'];t=a[:,0]
 diff=a[:,1]-a[:,2]-np.interp(t,b[:,0],b[:,1]-b[:,2]);cm=(a[:,1]+a[:,2])/2-np.interp(t,b[:,0],(b[:,1]+b[:,2])/2)
 rows.append(dict(initial_code=initial,peak_differential_change_v=float(max(abs(diff[(t>=2e-9)&(t<=4.9e-9)]))),settled_differential_change_v=float(np.interp(4.9e-9,t,diff)),returned_differential_error_v=float(np.interp(7.9e-9,t,diff)),peak_common_mode_change_v=float(max(abs(cm[(t>=2e-9)&(t<=4.9e-9)])))))
report=dict(status='actual_cdac_carry_diagnostic',image=image,baseline_sha256=sha(basepath),source_sha256=hashes,cases=cases,results=rows,limitations=['Ideal simultaneous100ps complementary gate commands, not physical code drivers.', 'Ideal rails, comparator held reset, no autonomous SAR or reference feedback.', 'Changing topology can inject charge; matching initial/final code does not guarantee exact return.'])
(P/'evidence/cdac-carry-transition.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(rows,indent=2))
