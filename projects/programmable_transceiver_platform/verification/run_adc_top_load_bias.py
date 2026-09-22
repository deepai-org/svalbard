"""Bounded bias sweep of actual reset-comparator/open-sampler loading."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-adc-top-load-bias';W.mkdir()
base=(P/'analog/adc/top_load.spice').read_text()
rows=[]
for cm in [1.45,1.65,1.85]:
 for diff in [-.4,0,.4]:
  name=f'cm{cm:g}_d{diff:g}';s=base
  for node,value in [('HP',cm+diff/2),('HN',cm-diff/2)]:
   source='VP' if node=='HP' else 'VN'
   s=s.replace(f'{source} {node} 0 DC 1.65',f'{source} {node} 0 DC {value:.12g}')
  s=s.replace('VIP IP 0 1.65',f'VIP IP 0 {cm+diff/2:.12g}').replace('VIN IN 0 1.65',f'VIN IN 0 {cm-diff/2:.12g}')
  s=s.replace('/work/load.dat',f'/work/{name}.dat')
  (W/(name+'.spice')).write_text(s)
  rows.append(dict(name=name,common_mode_v=cm,differential_v=diff))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
cmd=['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done']
subprocess.run(cmd,check=True,capture_output=True)
for row in rows:
 name=row['name'];log=(W/(name+'.log')).read_text().lower()
 assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(10,7) and np.isfinite(a).all()
 cp=-a[:,2]/(np.pi*a[:,0]);cn=a[:,4]/(np.pi*a[:,0]);unit=-a[:,6]/(2*np.pi*a[:,0])
 assert np.all(cp>0) and np.all(cn>0) and np.all(unit>0)
 row.update(positive_cap_ff=float(cp[0]*1e15),negative_cap_ff=float(cn[0]*1e15),positive_gain=float(256*unit[0]/(256*unit[0]+cp[0])),negative_gain=float(256*unit[0]/(256*unit[0]+cn[0])),artifacts_sha256={suffix:hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest() for suffix in ['.spice','.log','.dat']})
center=next(r for r in rows if r['common_mode_v']==1.65 and r['differential_v']==0)
prior=json.loads((P/'evidence/adc-top-load.json').read_text())
assert abs(center['positive_gain']-prior['predicted_gain'])<1e-10
for cm in [1.45,1.65,1.85]:
 plus=next(r for r in rows if r['common_mode_v']==cm and r['differential_v']==.4)
 minus=next(r for r in rows if r['common_mode_v']==cm and r['differential_v']==-.4)
 assert np.isclose(plus['positive_cap_ff'],minus['negative_cap_ff'],rtol=1e-6)
report=dict(status='static_bias_sensitivity_only',image=image,cases=rows,source_sha256=hashlib.sha256(base.encode()).hexdigest(),limitations=['Reset-state AC loading only; not time-varying comparator capacitance or conversion qualification.', 'Port susceptance under differential drive includes coupling; not a full capacitance matrix.', 'Selected bias points are sensitivity cases, not guaranteed operating bounds.'])
(P/'evidence/adc-top-load-bias.json').write_text(json.dumps(report,indent=2)+'\n')
print('9 cases; baseline and polarity controls passed')
print('cap fF range',min(r[k] for r in rows for k in ['positive_cap_ff','negative_cap_ff']),max(r[k] for r in rows for k in ['positive_cap_ff','negative_cap_ff']))
