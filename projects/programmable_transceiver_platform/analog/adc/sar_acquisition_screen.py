"""Changing-sample acquisition in the connected transistor SAR input hierarchy."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');rows=[]
for vin in (-.4,.4):
 for resistance in (100,300,1000):
  for changing in (False,True):
   name=f'vin{vin:g}_r{resistance}_change{int(changing)}';base=(B/f'vin{vin:g}.spice').read_text()
   d=base.replace('RIP SP IP 1k',f'RIP SP IP {resistance}').replace('RIN SN IN 1k',f'RIN SN IN {resistance}').replace('tran 10p 274n 0 10p','tran 10p 65n 0 10p').replace(f'/work/vin{vin:g}.dat',f'/work/{name}.dat')
   if changing:
    for source,node,sign in (('VIP','SP',1),('VIN','SN',-1)):
     final=1.65+sign*vin/2;initial=1.65-sign*vin/2
     d=d.replace(f'{source} {node} 0 {final}',f'{source} {node} 0 PWL(0 {initial} 50n {initial} 50.1n {final})')
   (O/(name+'.spice')).write_text(d)
   with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   rows.append(dict(name=name,input_difference_v=vin,resistance_ohm=resistance,changing=changing,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='paired_10ns_changing_input_acquisition_not_sample_rate_qualification',cases=rows,source_sha256=json.loads((B/'result.json').read_text())['source_sha256'],limitations=['Nominal matched TT 3.3V 27C; 0.8V differential step 10ns before hold, 100ps source transition.', 'Source resistance scenarios 100/300/1000ohm are fixtures, not a demonstrated RF/baseband output driver.', 'Conversion clocks have not yet started; paired acquisition error only, not conversion throughput or ENOB.', 'No noise/mismatch, previous conversion charge history or repeated reset/sample/conversion sequence.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed twelve paired acquisition cases.')
