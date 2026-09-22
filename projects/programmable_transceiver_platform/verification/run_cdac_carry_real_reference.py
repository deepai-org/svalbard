"""Earliest carry decision with transistor reference pair/reservoirs, prebiased OP."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
parser=argparse.ArgumentParser();parser.add_argument('--reset',action='store_true');args=parser.parse_args()
tag='cdac-carry-real-reference-reset' if args.reset else 'cdac-carry-real-reference'
W=R/('scratch/transceiver-'+tag);W.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
priorpath=P/'evidence/cdac-carry-decision.json';prior=json.loads(priorpath.read_text())
refpath=R/'scratch/transceiver-adc-sar8-reference-reservoir/typical_first1.spice'
ref=refpath.read_text();block=ref[ref.index('.include /screen/reference/adc_reference_pair.spice'):ref.index('VRST RN')]
block='VHR HR 0 2.15\nVLR LR 0 1.15\n'+block
cases=[]
for initial in [127,128]:
 name=f'code{initial}_delay100';parent=R/'scratch/transceiver-cdac-carry-decision'/(name+'.spice');old=parent.read_text()
 evidence=next(c for c in prior['cases'] if c['name']==name);assert sha(parent)==evidence['artifacts_sha256']['.spice']
 needle='VHIGH VH 0 2.15\nVLOW VL 0 1.15\n';assert old.count(needle)==1
 s=old.replace(needle,block);assert s.replace(block,needle)==old
 if args.reset:
  s,n=re.subn(r'^VC CLK 0 .*$', 'VC CLK 0 0',s,flags=re.M);assert n==1
 s=s.replace('v(QP) v(QN) v(CLK)','v(QP) v(QN) v(CLK) v(VH) v(VL) i(VREFSUP)')
 (W/(name+'.spice')).write_text(s);cases.append(dict(name=name,initial_code=initial,parent_sha256=sha(parent),target_sign=1 if initial==127 else -1))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
files=[P/'analog/adc/comparator.spice',P/'analog/adc/cdac8_mim.spice',P/'analog/adc/cdac8_scaled.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice']+list((P/'analog/reference').glob('*.spice'))
hashes={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert hashes=={str(p.relative_to(R)):sha(p) for p in files}
for c in cases:
 name=c['name'];log=(W/(name+'.log')).read_text().lower();assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==9 and np.isfinite(a).all() and a[-1,0]>=8e-9;t=a[:,0];mask=(t>=2e-9)&(t<=4.4e-9)
 pre=float(np.interp(2.2e-9,t,a[:,1]-a[:,2]));out=float(np.interp(4.4e-9,t,a[:,3]-a[:,4]))
 c.update(preclock_residue_v=pre,output_difference_v=out,correct_target_polarity=bool(c['target_sign']*out>2.97),initial_reference_span_v=float(a[0,6]-a[0,7]),reference_span_range_v=[float(min(a[mask,6]-a[mask,7])),float(max(a[mask,6]-a[mask,7]))],reference_supply_peak_a=float(max(abs(a[mask,8]))),artifacts_sha256={e:sha(W/(name+e)) for e in ['.spice','.log','.dat']})
report=dict(comparator_held_reset=args.reset,status='prebiased_real_reference_carry_diagnostic',image=image,source_sha256=hashes,prior_sha256=sha(priorpath),reference_donor_sha256=sha(refpath),cases=cases,limitations=['DC operating-point initialization, not cold startup.', 'Targets,20uA biases, supply and gate clocks remain ideal.', 'Single carry with one CDAC; not simultaneous I/Q or autonomous SAR.', 'Different reference DC span changes residue; ideal-rail target is not an accuracy specification.'])
(P/'evidence'/(tag+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print([(c['name'],c['preclock_residue_v'],c['correct_target_polarity'],c['reference_span_range_v']) for c in cases])
