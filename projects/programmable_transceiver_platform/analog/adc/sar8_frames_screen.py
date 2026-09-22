"""Three 50ns-spaced conversion frames with actual driver and decision circuitry."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');rows=[]
def pwl(points):return 'PWL('+' '.join(f'{t:g}n {v:g}' for t,v in points)+')'
def pulses(edges,width):
 points=[(0,0)]
 for edge in sorted(edges):points.extend([(edge,0),(edge+.1,3.3),(edge+width,3.3),(edge+width+.1,0)])
 return pwl(points)
for sign in (-1,1):
 name=f'first{sign}';base=(B/f'vin{sign*.4:g}_change0.spice').read_text();d=base
 holds=[70,120,170];values=[sign*.4,-sign*.4,sign*.4]
 updates=[5,112.5,162.5]+[hold+2.5+5*i for hold in holds for i in range(8)]
 clocks=[hold+.5+5*i for hold in holds for i in range(8)]
 rn=[(0,0),(1,0),(1.1,3.3),(110,3.3),(110.1,0),(111,0),(111.1,3.3),(160,3.3),(160.1,0),(161,0),(161.1,3.3)]
 start=[(0,3.3),(10,3.3),(10.1,0),(111,0),(111.1,3.3),(114,3.3),(114.1,0),(161,0),(161.1,3.3),(164,3.3),(164.1,0)]
 sample=[(0,3.3),(70,3.3),(70.1,0),(110,0),(110.1,3.3),(120,3.3),(120.1,0),(160,0),(160.1,3.3),(170,3.3),(170.1,0)]
 replacements={'VRST RN 0 ':pwl(rn),'VSTART START 0 ':pwl(start),'VUPDATE UPDATE 0 ':pulses(updates,1),'VS SC 0 ':pwl(sample),'VSB SCB 0 ':pwl([(t,3.3-v) for t,v in sample]),'VC CLK 0 ':pulses(clocks,2.9)}
 for source,node,polarity in (('VIP','SP',1),('VIN','SN',-1)):
  old=1.65-polarity*values[0]/2;points=[(0,old)]
  for hold,vin in zip(holds,values):
   new=1.65+polarity*vin/2;points.extend([(hold-10,old),(hold-9.9,new)]);old=new
  replacements[f'{source} {node} 0 ']=pwl(points)
 for prefix,value in replacements.items():
  assert len(re.findall('^'+re.escape(prefix),d,re.M))==1
  d=re.sub('^'+re.escape(prefix)+'.+$',prefix+value,d,flags=re.M)
 d=d.replace('tran 5p 114.9n 0 5p','tran 5p 209.9n 0 5p').replace(f'/work/vin{sign*.4:g}_change0.dat',f'/work/{name}.dat')
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
 rows.append(dict(name=name,hold_times_ns=holds,input_differences_v=values,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='three_external_phase_frames_50ns_spacing_not_qualified_adc',cases=rows,source_sha256=json.loads((B/'result.json').read_text())['source_sha256'],limitations=['External reset/start/clock/sample waveforms; no actual phase generator or output register.', 'Three frames in each polarity sequence, ideal capacitors/bias references and separate supplies.', 'No continuous transfer, ENOB, noise/mismatch/process or physical loading qualification.', 'Code must be observed before next reset; host capture timing unimplemented.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed two three-frame streams.')
