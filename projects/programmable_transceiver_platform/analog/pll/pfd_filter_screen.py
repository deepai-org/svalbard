import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for shift in (-5,0,5):
 name=f'phase{shift}'
 d=f'''* Transistor PFD at 25MHz, phase direction check
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/pll/pfd.spice
.include /screen/pll/charge_pump.spice
.include /screen/pll/loop_filter.spice
.temp 27
VDD VDD 0 3.3
VR REF 0 PULSE(0 3.3 40n 100p 100p 19.9n 40n)
VF FB 0 PULSE(0 3.3 {40+shift}n 100p 100p 19.9n 40n)
VRST RN 0 PWL(0 0 20n 0 20.1n 3.3)
XD REF FB RN UP DN VDD 0 pt_pfd
CU UP 0 50f
CD DN 0 50f
IP BP 0 20u
IN VDD BN 20u
VSENSE PUMP OUT 0
XF OUT 0 pt_loop_filter
.ic v(OUT)=1.08 v(XF.Z)=1.08
XCP UP DN PUMP BP BN VDD 0 pt_charge_pump
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 20p 801n 0 20p
wrdata /work/{name}.dat v(UP) v(DN) v(RN) i(VDD) i(VSENSE) v(OUT) v(XF.Z)
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==8 and np.isfinite(a).all()
 w=a[(a[:,0]>=120e-9)&(a[:,0]<=800e-9)];t=w[:,0]
 area=[float(np.trapezoid(w[:,c],t)/3.3) for c in (1,2)]
 reset=a[(a[:,0]>=5e-9)&(a[:,0]<=19e-9)]
 rows.append(dict(charge_per_cycle_c=float(np.trapezoid(w[:,5],t)/17),feedback_delay_ns=shift,equivalent_high_time_s=area,up_minus_down_s=area[0]-area[1],reset_output_max_v=float(reset[:,1:3].max()),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='connected_pfd_pump_passive_filter_open_loop',cases=rows,source_sha256={n:hashlib.sha256(Path('/screen/pll',n).read_bytes()).hexdigest() for n in ('pfd.spice','charge_pump.spice','loop_filter.spice')},limitations=['25MHz, TT 3.3V 27C, 50fF output loads plus actual charge-pump gates; Filter precharged to 1.08V, then released; not cold startup.', 'No frequency acquisition, dead-zone sweep, mismatch, supply perturbation or extracted timing.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
