"""First actual transistor loop connection; short transient is not lock evidence."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=Path('/chain/chain.spice').read_text()
assert base.count('VC CTRL 0 1.08')==1
extra='''.include /screen/pll/charge_pump.spice
.include /screen/pll/loop_filter.spice
IP BPCP 0 20u
IN VDIV BNCP 20u
XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump
VSENSE PUMP CTRL 0
XFILT CTRL 0 pt_loop_filter
.ic v(CTRL)=1.08 v(XFILT.Z)=1.08
'''
d=base.replace('VC CTRL 0 1.08\n','').replace('.control',extra+'.control')
d=d.replace('/work/chain.dat','/work/closed.dat').replace('v(UP) v(DN)\n','v(UP) v(DN) v(CTRL) v(XFILT.Z) i(VSENSE) v(REF)\n')
p=O/'closed.spice';p.write_text(d)
with (O/'closed.log').open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
a=np.loadtxt(O/'closed.dat',skiprows=1);assert a.shape[1]==18 and np.isfinite(a).all() and a[-1,0]>320e-9
rows=[]
for lo,hi in ((100,200),(220,320)):
 w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0];v=w[:,1];i=np.where((v[:-1]<0)&(v[1:]>=0))[0];e=t[i]+(t[i+1]-t[i])*(-v[i])/(v[i+1]-v[i])
 rows.append(dict(window_ns=[lo,hi],vco_frequency_hz=float((len(e)-1)/(e[-1]-e[0])) if len(e)>3 else None,control_range_v=[float(w[:,14].min()),float(w[:,14].max())],control_mean_v=float(np.trapezoid(w[:,14],t)/(t[-1]-t[0])),gate_range_v=[float(w[:,10].min()),float(w[:,10].max())]))
r=dict(status='short_closed_transistor_loop_not_lock_qualification',windows=rows,artifacts_sha256={s:hashlib.sha256((O/('closed'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},limitations=['321ns with precharged filter, seeded VCO and prebiased LNA; no cold startup.', 'Only a few reference cycles, no lock/acquisition/stability or phase-noise claim.', 'Actual divide128/PFD/pump/filter/VCO, but ideal external bias sources/reference/sampling clocks.', 'Filter values are preliminary; no PVT/mismatch or physical parasitics.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
