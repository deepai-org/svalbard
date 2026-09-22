"""Nominal decision/reset timing with finite source resistance, not an ADC."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work'); rows=[]
for cm in (0.8,1.2,1.65):
 for diff in (-.01,-.001,.001,.01):
  name=f'cm{cm:g}_d{diff:g}'
  d=f'''* ADC comparator nominal screen: alternating input polarity each cycle
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/adc/comparator.spice
.temp 27
VDD VDD 0 3.3
VCLK CLK 0 PULSE(0 3.3 5n 100p 100p 2.4n 5n)
VIP SP 0 PULSE({cm+diff/2} {cm-diff/2} 8n 100p 100p 4.9n 10n)
VIN SN 0 PULSE({cm-diff/2} {cm+diff/2} 8n 100p 100p 4.9n 10n)
RIP SP INP 1k
RIN SN INN 1k
CIP INP 0 1p
CIN INN 0 1p
XC INP INN CLK QP QN VDD 0 pt_adc_comparator
CP QP 0 50f
CN QN 0 50f
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 5p 51n 0 5p
wrdata /work/{name}.dat v(CLK) v(QP) v(QN) v(INP) v(INN) i(VDD) v(SP) v(SN)
.endc
.end
'''
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log: subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==9 and np.isfinite(a).all()
  cycles=[]
  for start in range(10,46,5):
   w=a[(a[:,0]>=(start+1.9)*1e-9)&(a[:,0]<=(start+2.3)*1e-9)]
   # Polarity derives from settled external stimulus, not regenerated kickback.
   sign=np.sign(np.mean(w[:,7]-w[:,8]))
   high=w[:,2] if sign>0 else w[:,3];low=w[:,3] if sign>0 else w[:,2]
   reset=a[(a[:,0]>=(start+4.5)*1e-9)&(a[:,0]<=(start+4.9)*1e-9)]
   cycles.append(dict(start_ns=start,input_sign=float(sign),correct_rails=bool(high.min()>2.97 and low.max()<.33),high_min_v=float(high.min()),low_max_v=float(low.max()),reset_min_v=float(reset[:,2:4].min())))
  rows.append(dict(name=name,common_mode_v=cm,initial_difference_v=diff,cycles=cycles,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='nominal_clocked_comparator_screen_not_adc',cases=rows,source_sha256=hashlib.sha256(Path('/screen/adc/comparator.spice').read_bytes()).hexdigest(),limitations=['TT 3.3V 27C, deterministic matched devices; no offset, noise, process or statistical yield.', '200MHz ideal clock; ideal stimulus behind 1kohm/1pF per input, 50fF output loads.', 'No CDAC, sample/hold integration, references, conversion controller or output latch.', 'Alternating deterministic differences do not establish ENOB, metastability probability or ADC sample rate.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([dict(name=c['name'],all_decisions_correct=all(x['correct_rails'] for x in c['cycles']),minimum_reset_v=min(x['reset_min_v'] for x in c['cycles'])) for c in rows],indent=2))
