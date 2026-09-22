"""Actual sampler/comparator with floating PDK capacitor loads; no switched CDAC."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
parser=argparse.ArgumentParser();parser.add_argument('--cdac',action='store_true');args=parser.parse_args()
tag='adc-cdac-kickback' if args.cdac else 'adc-floating-kickback'
W=R/('scratch/transceiver-'+tag);W.mkdir()
base=(P/'analog/adc/top_load.spice').read_text();cases=[]
for diff in [-.001,.001]:
 for clocked in [False,True]:
  name=f'd{diff:g}_clk{int(clocked)}'
  s=base.replace('VP HP 0 DC 1.65 AC .5\n','').replace('VN HN 0 DC 1.65 AC .5 180\n','')
  s=s.replace('VIP IP 0 1.65',f'VIP IP 0 {1.65+diff/2:.12g}').replace('VIN IN 0 1.65',f'VIN IN 0 {1.65-diff/2:.12g}')
  s=s.replace('VS SC 0 0','VS SC 0 PWL(0 3.3 1n 3.3 1.1n 0)').replace('VSB SCB 0 3.3','VSB SCB 0 PWL(0 0 1n 0 1.1n 3.3)')
  caps='\n'.join(f'X{leg}{k} H{leg} 0 cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u' for leg in ['P','N'] for k in range(256))
  if args.cdac:
   controls='\n'.join(f'VB{k} B{k} 0 {3.3 if k<7 else 0}\nVBB{k} BB{k} 0 {0 if k<7 else 3.3}' for k in range(8))
   ports=' '.join(f'B{k} BB{k}' for k in range(8))
   caps=f'.include /screen/adc/cdac8_scaled.spice\n.include /screen/adc/cdac8_mim.spice\nVHIGH VH 0 2.15\nVLOW VL 0 1.15\n{controls}\nXD HP HN VH VL {ports} VDD 0 pt_cdac8_mim'
  s=s.replace('.control',caps+'\n.control')
  if clocked:s=s.replace('VC CLK 0 0','VC CLK 0 PWL(0 0 2n 0 2.1n 3.3 5n 3.3 5.1n 0)')
  s=s.replace('ac dec 3 1meg 1g','tran 1p 8n 0 1p').replace('wrdata /work/load.dat i(VP) i(VN) i(VU)',f'wrdata /work/{name}.dat v(HP) v(HN) v(QP) v(QN) v(CLK)')
  (W/(name+'.spice')).write_text(s);cases.append(dict(name=name,differential_v=diff,clocked=clocked))
image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[P/'analog/adc/top_load.spice',P/'analog/adc/comparator.spice',R/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice']
if args.cdac:files += [P/'analog/adc/cdac8_scaled.spice',P/'analog/adc/cdac8_mim.spice']
hashes={str(p.relative_to(R)):sha(p) for p in files}
subprocess.run(['docker','run','--rm','--platform','linux/arm64','--network','none','--cpus','1','--memory','2g','--entrypoint','/bin/bash','-v',f'{P}/analog:/screen:ro','-v',f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro','-v',f'{W}:/work','--workdir','/work',image,'-lc','for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'],check=True,capture_output=True)
assert hashes=={str(p.relative_to(R)):sha(p) for p in files}
arrays={}
for c in cases:
 name=c['name'];log=(W/(name+'.log')).read_text().lower()
 assert 'ngspice-46 done' in log and not any(x in log for x in ['warning','error','aborted'])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==6 and a[-1,0]>=8e-9 and np.isfinite(a).all();arrays[name]=a
 c['artifacts_sha256']={ext:sha(W/(name+ext)) for ext in ['.spice','.log','.dat']}
rows=[]
for diff in [-.001,.001]:
 a=arrays[f'd{diff:g}_clk1'];b=arrays[f'd{diff:g}_clk0'];t=a[(a[:,0]>=2e-9)&(a[:,0]<=4.9e-9),0]
 differential=np.interp(t,a[:,0],a[:,1]-a[:,2])-np.interp(t,b[:,0],b[:,1]-b[:,2])
 common=np.interp(t,a[:,0],(a[:,1]+a[:,2])/2)-np.interp(t,b[:,0],(b[:,1]+b[:,2])/2)
 pre=float(np.interp(1.9e-9,a[:,0],a[:,1]-a[:,2]));output=float(np.interp(4.9e-9,a[:,0],a[:,3]-a[:,4]))
 assert np.sign(pre)==np.sign(diff) and np.sign(output)==np.sign(diff)
 rows.append(dict(input_differential_v=diff,held_before_clock_v=pre,peak_clock_induced_differential_v=float(np.max(abs(differential))),peak_clock_induced_common_mode_v=float(np.max(abs(common))),output_difference_v=output))
report=dict(status='fixed_code_cdac_clock_diagnostic' if args.cdac else 'floating_capacitor_load_diagnostic',image=image,source_sha256=hashes,cases=cases,results=rows,limitations=['Actual CDAC switches at fixed code127 and ideal rails; no SAR transitions or physical reference regulation.' if args.cdac else '256 grounded MIM units per side approximate array capacitance; switched CDAC and actual references absent.', 'Paired reset subtraction separates clock effect; sampler acquisition/injection still affects held value.', 'Nominal two inputs, one clock slew, no mismatch or noise; not ADC qualification.'])
(P/'evidence'/(tag+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
