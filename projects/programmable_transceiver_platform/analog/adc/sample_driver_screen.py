"""Actual input buffer replacing the ideal low source resistance assumption."""
import hashlib,json,subprocess
from pathlib import Path

def main(variant='nominal'):
 if variant not in ('nominal','headroom','longmirror'):
  raise ValueError('Unknown sampling driver variant')
 driver='sample_driver'+('' if variant=='nominal' else '_'+variant)
 status='longmirror_sampling_driver_nominal_screen' if variant=='longmirror' else 'transistor_sampling_driver_first_nominal_screen'
 O=Path('/work');B=Path('/baseline');rows=[]
 for vin in (-.4,.4):
  for changing in (False,True):
   name=f'vin{vin:g}_change{int(changing)}';base=(B/f'vin{vin:g}_r1000_change{int(changing)}.spice').read_text()
   extra=f'''.include /screen/adc/{driver}.spice
VBUF VBUF 0 3.3
IBN VBUF BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VBUF VBUF pfet_03v3 w=8u l=.5u
XBPDRV GP IP BN BP VBUF 0 pt_{driver}
XBNDRV GN IN BN BP VBUF 0 pt_{driver}
'''
   d=base.replace('RIP SP IP 1000','RIP SP GP 1000').replace('RIN SN IN 1000','RIN SN GN 1000').replace('.control',extra+'.control').replace(f'/work/vin{vin:g}_r1000_change{int(changing)}.dat',f'/work/{name}.dat').replace('v(KEEPP) v(KEEPN)\n','v(KEEPP) v(KEEPN) v(IP) v(IN) v(GP) v(GN) i(VBUF) v(BN) v(BP)\n')
   (O/(name+'.spice')).write_text(d)
   with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   rows.append(dict(name=name,input_difference_v=vin,changing=changing,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
 sources=json.loads((B/'result.json').read_text())['source_sha256'];sources[f'/screen/adc/{driver}.spice']=hashlib.sha256(Path(f'/screen/adc/{driver}.spice').read_bytes()).hexdigest()
 r=dict(status=status,cases=rows,source_sha256=sources,limitations=['TT 3.3V 27C matched devices; 1pF compensation and ideal matched capacitors.', 'Diode-connected bias devices driven by ideal 20uA sources; complete reference generation absent.', 'Ideal separate buffer supply; no supply/ground coupling, noise, mismatch or extracted loading.', 'Constant and 0.8V step inputs from 1kohm sources; no conversion or repeated-frame qualification.', 'No loop stability margin, startup or broad load/common-mode qualification.'])
 (O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed four transistor sampling-driver cases.')

if __name__=='__main__':main()
