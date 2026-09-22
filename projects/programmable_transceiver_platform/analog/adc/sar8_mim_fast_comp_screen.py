"""Controlled half-compensation candidate in the connected PDK-capacitor ADC."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
 for line in ('XBPDRV GP IP BN BP VBUF 0 pt_sample_driver_headroom','XBNDRV GN IN BN BP VBUF 0 pt_sample_driver_headroom'):
  assert d.count(line+'\n')==1;d=d.replace(line+'\n',line+' CC=.5p\n')
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
 rows.append(dict(name=name,corner=c['corner'],first_sign=c['first_sign'],baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log')}));print('Completed '+name,flush=True)
(O/'result.json').write_text(json.dumps(dict(status='half_compensation_candidate_unverified',cases=rows,source_sha256=base['source_sha256'],limitations=['Only compensation capacitance changed; still ideal and not process-qualified.', 'No adoption or accuracy claim until connected waveform audit.']),indent=2)+'\n')
