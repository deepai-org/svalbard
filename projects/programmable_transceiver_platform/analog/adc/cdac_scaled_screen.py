"""Actual FET-switched CDAC and sampler/comparator; externally scripted code steps."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for code in (64,127,129,192):
 for active in (False,True):
  name=f'code{code}_a{int(active)}';controls=[]
  for bit in range(8):
   initial=(128>>bit)&1; final=(code>>bit)&1
   for complement in (False,True):
    node=f'B{bit}'+('B' if complement else '')
    v0=3.3*(1-initial if complement else initial);v1=3.3*(1-final if complement else final)
    controls.append(f'V{node} {node} 0 PWL(0 {v0} 12n {v0} 12.1n {v1} 22n {v1} 22.1n {v0})')
  ports=' '.join(f'B{i} B{i}B' for i in range(8))
  clock='PULSE(0 3.3 16n 100p 100p 2.4n 10n)' if active else '0'
  d=f'''* Top plate sampled CDAC with actual switch bank and comparator
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/adc/comparator.spice
.include /screen/adc/cdac8_scaled.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
.temp 27
VDD VDD 0 3.3
VIP SP 0 1.6505
VIN SN 0 1.6495
RIP SP IP 1k
RIN SN IN 1k
VHR HR 0 2.15
VLR LR 0 1.15
RHR HR VH 10
RLR LR VL 10
CHR VH 0 10p
CLR VL 0 10p
VS SC 0 PWL(0 3.3 10n 3.3 10.1n 0)
VSB SCB 0 PWL(0 0 10n 0 10.1n 3.3)
VC CLK 0 {clock}
{chr(10).join(controls)}
XS IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate
XD HP HN VH VL {ports} VDD 0 pt_cdac8_scaled
XC HP HN CLK QP QN VDD 0 pt_adc_comparator
CP QP 0 50f
CN QN 0 50f
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 2p 31n 0 2p
wrdata /work/{name}.dat v(HP) v(HN) v(QP) v(QN) v(CLK) v(VH) v(VL) i(VHR) i(VLR)
.endc
.end
'''
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==10 and np.isfinite(a).all()
  rows.append(dict(name=name,code=code,active=active,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='scaled_switch_cdac_step_screen_not_adc',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('/screen/adc/comparator.spice'),Path('/screen/adc/cdac8_scaled.spice'),Path('/wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice'))},limitations=['Nominal matched TT 3.3V 27C; ideal capacitors 20fF unit, 5.12pF per side.', 'Ideal reference sources behind 10ohm and 10pF local capacitance; not implemented reference drivers.', 'Ideal external code/complement and clock waveforms; no SAR controller or output latch.', 'Two scripted decisions with code return, not a complete conversion or transfer curve.', 'No mismatch, capacitor nonlinearity, noise, physical parasitics, previous-sample acquisition or ENOB qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed',len(rows),'CDAC code-step cases.')
