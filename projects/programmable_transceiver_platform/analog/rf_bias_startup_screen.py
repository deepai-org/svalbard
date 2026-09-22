#!/usr/bin/env python3
"""Cold RF bias with oscillator rail held off; not whole-chip startup."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');S=Path('/screen');base=(S/'rf_candidate_op.spice').read_text().split('.control')[0];rows=[]
for scale in (.5,1,2):
 name=f'rc{scale:g}'
 core=(S/'rf_rx_candidate.spice').read_text().replace('RB GATE RFBIAS 1meg',f'RB GATE RFBIAS {scale*1e6:g}')
 cp=O/(name+'_core.spice');cp.write_text(core)
 d=base.replace('/screen/rf_rx_candidate.spice',str(cp)).replace('VDD RFVDD 0 3.3','VDD RFVDD 0 PWL(0 0 1u 3.3)').replace('VPLL PLLVDD 0 3.3','VPLL PLLVDD 0 0').replace('VB RFBIAS 0 1.5','VB RFBIAS 0 PWL(0 0 1u 1.5)').replace('VBB BBBIAS 0 2.25','VBB BBBIAS 0 PWL(0 0 1u 2.25)').replace('VC CTRL 0 1.08','VC CTRL 0 0').replace('VSCB SCB 0 3.3','VSCB SCB 0 PWL(0 0 1u 3.3)')
 d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 20n 200u 0 20n uic
wrdata /work/{name}.dat v(XRX.GATE) v(XRX.SOURCE) v(XRX.DRAIN) i(VDD)
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a[-1,0]>=200e-6
 inband=abs(a[:,1]-1.5)<=.015
 bad=np.where(~inband)[0];j=int(bad[-1]+1) if len(bad) else 0
 settle=float(a[j,0]) if j<len(a) else None
 row=dict(resistance_scale=scale,gate_final_v=float(a[-1,1]),source_final_v=float(a[-1,2]),gate_1percent_settling_s=settle,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','_core.spice','.dat','.log')});rows.append(row);print(json.dumps(row),flush=True)
r=dict(status='cold_bias_with_pll_rail_off_not_complete_startup',cases=rows,limitations=['Ideal 1us external supply and bias ramps; bias generators not implemented.', 'Oscillator rail held at zero and control at zero; no oscillator release/startup test.', '0.5x/2x resistance are sensitivity scenarios, not process bounds.', 'Gate settling threshold 15mV is diagnostic, not receiver accuracy qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
