"""First transistor decision loop. Conservative external phase timing, not throughput qualification."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for vin in (-.4,-.123,.123,.4):
 name=f'vin{vin:g}'
 update=['0 0']
 for edge in [5]+list(range(77,113,5)):update += [f'{edge}n 0',f'{edge+.1}n 3.3',f'{edge+1}n 3.3',f'{edge+1.1}n 0']
 ports=' '.join(f'B{i} B{i}B' for i in range(8));bits=' '.join(f'D{i}' for i in range(8))
 drivers='\n'.join(f'XDRV{i} D{i} B{i} B{i}B VDRV 0 pt_adc_code_small_driver WEIGHT={2**i}' for i in range(8))
 d=f'''* Actual GF180 SAR decision feedback, external phase clocks
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/pll/pfd.spice
.include /screen/adc/sar8_control.spice
.include /screen/adc/comparator.spice
.include /screen/adc/cdac8_scaled.spice
.include /screen/adc/code_driver_small.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
.temp 27
VDD VDD 0 3.3
VLOG VLOG 0 3.3
VDRV VDRV 0 3.3
VIP SP 0 {1.65+vin/2}
VIN SN 0 {1.65-vin/2}
RIP SP IP 1k
RIN SN IN 1k
VHR HR 0 2.15
VLR LR 0 1.15
RHR HR VH 10
RLR LR VL 10
CHR VH 0 10p
CLR VL 0 10p
VRST RN 0 PWL(0 0 1n 0 1.1n 3.3)
VSTART START 0 PWL(0 3.3 10n 3.3 10.1n 0)
VUPDATE UPDATE 0 PWL({' '.join(update)})
VS SC 0 PWL(0 3.3 60n 3.3 60.1n 0)
VSB SCB 0 PWL(0 0 60n 0 60.1n 3.3)
VC CLK 0 PULSE(0 3.3 75n 100p 100p 2.8n 5n)
XS IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate
XD HP HN VH VL {ports} VDD 0 pt_cdac8_scaled
XC HP HN CLK QP QN VDD 0 pt_adc_comparator
XOP0 QP QPB VLOG 0 pt_inv
XOP1 QPB KEEPP VLOG 0 pt_inv
XON0 QN QNB VLOG 0 pt_inv
XON1 QNB KEEPN VLOG 0 pt_inv
CP QP 0 50f
CN QN 0 50f
XCTL KEEPN UPDATE START RN {bits} DONE VLOG 0 pt_sar8_control
{drivers}
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 5p 114.9n 0 5p
wrdata /work/{name}.dat v(HP) v(HN) v(QP) v(QN) v(CLK) v(UPDATE) v(DONE) {' '.join('v(D'+str(i)+')' for i in range(8))} {' '.join('v(XCTL.T'+str(i)+')' for i in range(8))} i(VLOG) i(VDRV) v(KEEPP) v(KEEPN)
.endc
.end
'''
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==28 and np.isfinite(a).all()
 final=a[(a[:,0]>114e-9)&(a[:,0]<114.8e-9)];code=sum((np.mean(final[:,8+i])>1.65)*2**i for i in range(8))
 rows.append(dict(name=name,input_difference_v=vin,final_code=int(code),done_min_v=float(final[:,7].min()),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
sources=[Path('/screen/pll/pfd.spice')]+[Path('/screen/adc')/f for f in ('sar8_control.spice','comparator.spice','cdac8_scaled.spice','code_driver_small.spice')]+[Path('/wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice')]
r=dict(status='buffered_sar_5ns_bit_timing_screen_not_sample_rate_qualification',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},limitations=['Nominal matched TT 3.3V 27C, ideal matched capacitors/references/supplies.', 'External START/reset/update/comparator/sample clocks; phase generation not implemented.', '5ns bit interval with long initialization/acquisition; repeated 20--40MS/s conversions not demonstrated.', 'Four constant input conversions only, no transfer/noise/mismatch or changing-sample qualification.', 'Output bit polarity is complementary to ascending input; no host output register/interface.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
