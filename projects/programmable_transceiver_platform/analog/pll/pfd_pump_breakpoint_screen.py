"""Actual PFD/pump/filter reduced numerical diagnostic; no autonomous oscillator."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');rows=[]
for kind,folder in (('pulse','/pulse'),('pwl','/pwl')):
 ref=next(x for x in (Path(folder)/'closed.spice').read_text().splitlines() if x.startswith('VREF '))
 for skew in (-10,0,10):
  name=f'{kind}_skew{skew}'
  d=f'''* Active reduced PLL fixture; ideal feedback stimulus
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/pll/pfd.spice
.include /screen/pll/charge_pump.spice
.include /screen/pll/loop_filter.spice
.temp 27
VDIV VDIV 0 3.3
{ref}
VFB FB 0 PULSE(0 3.3 {100+skew}n 100p 100p 25.5n 51.2n)
VRN RN 0 PWL(0 0 90n 0 90.1n 3.3)
XPFD REF FB RN UP DN VDIV 0 pt_pfd
CU UP 0 50f
CD DN 0 50f
IP BPCP 0 20u
IN VDIV BNCP 20u
XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump
VSENSE PUMP CTRL 0
XFILT CTRL 0 pt_loop_filter
.ic v(CTRL)=1.08 v(XFILT.Z)=1.08
.options method=gear maxord=2
.control
save v(CTRL) v(UP) v(DN)
tran 2p 3201n 0 2p uic
meas tran final_control FIND v(CTRL) AT=3201n
meas tran min_control MIN v(CTRL) FROM=100n TO=3201n
meas tran max_control MAX v(CTRL) FROM=100n TO=3201n
.endc
.end
'''
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=600)
  rows.append(dict(name=name,kind=kind,feedback_skew_ns=skew,returncode=r.returncode,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.log')}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,r.returncode,flush=True)
sources=[Path('/screen/pll')/n for n in ('pfd.spice','charge_pump.spice','loop_filter.spice')]
(O/'result.json').write_text(json.dumps(dict(status='reduced_active_PLL_diagnostic_unverified',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
