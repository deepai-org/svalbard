"""Instrument CDAC rail currents; gate attribution on voltage reproduction."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-carry-rail-probes';W.mkdir()
B=R/'scratch/transceiver-cdac-carry-real-reference-reset';source=P/'evidence/cdac-carry-real-reference-reset.json';prior=json.loads(source.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cases=[]
for case in prior['cases']:
 name=case['name'];old=(B/(name+'.spice')).read_text();assert sha(B/(name+'.spice'))==case['artifacts_sha256']['.spice']
 assert old.count('XD HP HN VH VL ')==1
 s=old.replace('XD HP HN VH VL ','VPROBEH VH VHCD 0\nVPROBEL VL VLCD 0\nXD HP HN VHCD VLCD ')
 assert s.replace('VPROBEH VH VHCD 0\nVPROBEL VL VLCD 0\nXD HP HN VHCD VLCD ','XD HP HN VH VL ')==old
 s=s.replace('i(VREFSUP)','i(VREFSUP) i(VPROBEH) i(VPROBEL)')
 (W/(name+'.spice')).write_text(s);cases.append(dict(name=name,parent_sha256=sha(B/(name+'.spice'))))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[R/p for p in prior['source_sha256']];before={str(p.relative_to(R)):sha(p) for p in files};assert before==prior['source_sha256']
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert before=={str(p.relative_to(R)):sha(p) for p in files}
for c,parent in zip(cases,prior['cases'],strict=True):
 name=c['name'];log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);p=B/(name+'.dat');assert sha(p)==parent['artifacts_sha256']['.dat'];b=np.loadtxt(p,skiprows=1)
 assert a.shape[1]==11 and np.isfinite(a).all() and a[-1,0]>=8e-9
 t=np.unique(np.r_[2e-9,a[(a[:,0]>2e-9)&(a[:,0]<4.4e-9),0],b[(b[:,0]>2e-9)&(b[:,0]<4.4e-9),0],4.4e-9])
 errors={str(col):float(max(abs(np.interp(t,a[:,0],a[:,col])-np.interp(t,b[:,0],b[:,col])))) for col in [1,2,6,7]}
 c.update(max_voltage_difference_v=errors,voltage_reproduction_pass=max(errors.values())<=10e-6,artifacts_sha256={e:sha(W/(name+e)) for e in ['.spice','.log','.dat']})
report=dict(status='rail_probe_reproduction_checked',voltage_tolerance_v=10e-6,source_sha256=before,image=image,parent_report_sha256=sha(source),cases=cases,limitations=['10uV reproduction threshold declared before run; diagnostic scope2–4.4ns only.', 'Positive probe current means reference rail into CDAC; supply current is a different quantity.', 'Do not attribute currents to unprobed baseline if voltage reproduction fails.'])
(P/'evidence/carry-rail-probes.json').write_text(json.dumps(report,indent=2)+'\n');print([(c['name'],c['voltage_reproduction_pass'],c['max_voltage_difference_v']) for c in cases])
