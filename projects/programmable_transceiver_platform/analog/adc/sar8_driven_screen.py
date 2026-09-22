"""Connect the actual acquisition driver to all eight fast transistor SAR decisions."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');rows=[]
extra='''.include /screen/adc/sample_driver_headroom.spice
VBUF VBUF 0 3.3
IBN VBUF BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VBUF VBUF pfet_03v3 w=8u l=.5u
XBPDRV GP IP BN BP VBUF 0 pt_sample_driver_headroom
XBNDRV GN IN BN BP VBUF 0 pt_sample_driver_headroom
'''
for vin in (-.4,.4):
 for changing in (False,True):
  name=f'vin{vin:g}_change{int(changing)}';base=(B/f'vin{vin:g}.spice').read_text()
  d=base.replace('RIP SP IP 1k','RIP SP GP 1k').replace('RIN SN IN 1k','RIN SN GN 1k').replace('.control',extra+'.control').replace(f'/work/vin{vin:g}.dat',f'/work/{name}.dat').replace('v(KEEPP) v(KEEPN)\n','v(KEEPP) v(KEEPN) v(IP) v(IN) i(VBUF)\n')
  if changing:
   for source,node,sign in (('VIP','SP',1),('VIN','SN',-1)):
    final=1.65+sign*vin/2;initial=1.65-sign*vin/2
    d=d.replace(f'{source} {node} 0 {final}',f'{source} {node} 0 PWL(0 {initial} 50n {initial} 50.1n {final})')
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==31 and np.isfinite(a).all()
  final=a[(a[:,0]>=114e-9)&(a[:,0]<=114.8e-9)];code=sum(int(np.mean(final[:,8+i])>1.65)*2**i for i in range(8))
  rows.append(dict(name=name,input_difference_v=vin,changing=changing,final_code=code,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
sources=json.loads((B/'result.json').read_text())['source_sha256'];sources['/screen/adc/sample_driver_headroom.spice']=hashlib.sha256(Path('/screen/adc/sample_driver_headroom.spice').read_bytes()).hexdigest()
r=dict(status='connected_driver_and_fast_sar_single_conversion_screen',cases=rows,source_sha256=sources,limitations=['TT 3.3V 27C matched devices; ideal capacitors, references, phase clocks and separate supplies.', 'Both polarities of 0.8V step 10ns before hold, with constant-input controls; not a transfer curve.', 'One conversion per simulation with long initial state preparation; not repeated 20--40MS/s frames.', 'No noise/mismatch, phase-generator/output-interface implementation or physical parasitics.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps([dict(name=c['name'],code=c['final_code']) for c in rows],indent=2))
