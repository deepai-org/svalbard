"""Paired evaluate/reset-held tests isolate comparator disturbance of held charge."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for cm in (1.2,1.65):
 for cap in (1,5,10):
  for sign in (-1,1):
   for active in (False,True):
    name=f'cm{cm:g}_c{cap}_s{sign}_a{int(active)}'
    clock='PULSE(0 3.3 12n 100p 100p 2.4n 20n)' if active else '0'
    d=f'''* Held-input comparator: same circuit in active and reset-held controls
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/adc/comparator.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
.temp 27
VDD VDD 0 3.3
VIP SP 0 {cm+sign*.0005}
VIN SN 0 {cm-sign*.0005}
RIP SP IP 1k
RIN SN IN 1k
VS SC 0 PWL(0 3.3 10n 3.3 10.1n 0)
VSB SCB 0 PWL(0 0 10n 0 10.1n 3.3)
VC CLK 0 {clock}
XS IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate
CHP HP 0 {cap}p
CHN HN 0 {cap}p
XC HP HN CLK QP QN VDD 0 pt_adc_comparator
CP QP 0 50f
CN QN 0 50f
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 2p 20n 0 2p
wrdata /work/{name}.dat v(HP) v(HN) v(QP) v(QN) v(CLK) v(SC) v(SCB) i(VDD)
.endc
.end
'''
    (O/(name+'.spice')).write_text(d)
    with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==9 and np.isfinite(a).all()
    w=a[(a[:,0]>=13.9e-9)&(a[:,0]<=14.3e-9)];hi,lo=(3,4) if sign>0 else (4,3)
    rows.append(dict(name=name,common_mode_v=cm,hold_cap_pf=cap,sign=sign,active=active,correct_rails=bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33) if active else None,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='paired_held_input_comparator_disturbance_not_adc',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('/screen/adc/comparator.spice'),Path('/wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice'))},limitations=['Nominal TT 3.3V 27C matched devices, 1mV differential input, ideal clock sources.', 'DC operating point initially tracks constant input; not acquisition from arbitrary previous sample or cold startup.', 'Hold capacitances 1/5/10pF are deliberate load scenarios, not manufacturing bounds.', 'Reset-held paired control separates clocked-comparator disturbance from sampler turnoff, but no CDAC/reference or conversion controller.', 'No mismatch, thermal noise, extracted parasitics, repeated SAR decisions or ENOB evidence.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print('Completed',len(rows),'paired held-input cases;',sum(c['correct_rails'] is True for c in rows),'of 12 active cases pass rails.')
