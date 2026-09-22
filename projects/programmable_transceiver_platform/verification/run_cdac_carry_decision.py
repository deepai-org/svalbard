"""Comparator decisions after actual CDAC carry; ideal rails and gate commands."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-carry-decision';W.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
priorpath=P/'evidence/cdac-carry-transition.json';prior=json.loads(priorpath.read_text());cases=[]
for initial in [127,128]:
 name=f'code{initial}_switch1';parent=R/'scratch/transceiver-cdac-carry-transition'/(name+'.spice')
 case=next(c for c in prior['cases'] if c['name']==name);assert sha(parent)==case['artifacts_sha256']['.spice']
 sign=1 if initial==127 else -1
 input_diff=sign*(.001-.00777243)
 for delay_ps in [100,200,500]:
  name=f'code{initial}_delay{delay_ps}';s=parent.read_text();edge=2.1+delay_ps/1000
  s,n=re.subn(r'^VIP IP 0 .*$',f'VIP IP 0 {1.65+input_diff/2:.12g}',s,flags=re.M);assert n==1
  s,n=re.subn(r'^VIN IN 0 .*$',f'VIN IN 0 {1.65-input_diff/2:.12g}',s,flags=re.M);assert n==1
  s=s.replace('VC CLK 0 0',f'VC CLK 0 PWL(0 0 {edge:g}n 0 {edge+.1:g}n 3.3 4.5n 3.3 4.6n 0)')
  s=re.sub(r'wrdata /work/\S+ ',f'wrdata /work/{name}.dat ',s)
  (W/(name+'.spice')).write_text(s);cases.append(dict(name=name,initial_code=initial,delay_ps=delay_ps,edge_ns=edge,input_diff_v=input_diff,target_sign=sign,parent_sha256=sha(parent)))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[P/'analog/adc/comparator.spice',P/'analog/adc/cdac8_mim.spice',P/'analog/adc/cdac8_scaled.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice'];hashes={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert hashes=={str(p.relative_to(R)):sha(p) for p in files}
for c in cases:
 name=c['name'];log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==6 and np.isfinite(a).all() and a[-1,0]>=8e-9;t=a[:,0];edge=c['edge_ns']*1e-9
 pre=float(np.interp(edge,t,a[:,1]-a[:,2]));out=float(np.interp(4.4e-9,t,a[:,3]-a[:,4]))
 window=(t>=edge)&(t<=4.4e-9);resolved=np.flatnonzero(window&(c['target_sign']*(a[:,3]-a[:,4])>2.97))
 c.update(preclock_residue_v=pre,preclock_common_mode_v=float(np.interp(edge,t,(a[:,1]+a[:,2])/2)),output_difference_v=out,correct_target_polarity=bool(c['target_sign']*out>2.97),first_resolved_after_edge_ps=float((t[resolved[0]]-edge)*1e12) if len(resolved) else None,artifacts_sha256={e:sha(W/(name+e)) for e in ['.spice','.log','.dat']})
report=dict(status='nominal_carry_decision_diagnostic',image=image,source_sha256=hashes,prior_sha256=sha(priorpath),cases=cases,limitations=['Near±1mV target only, nominal devices, ideal rails and100ps ideal control edges.', 'Resolution time uses output crossing, not latched decision validity or metastability probability.', 'Reference regulation, actual code/clock drivers, noise and mismatch absent.'])
(P/'evidence/cdac-carry-decision.json').write_text(json.dumps(report,indent=2)+'\n')
print([(c['name'],c['preclock_residue_v'],c['correct_target_polarity'],c['first_resolved_after_edge_ps']) for c in cases])
