"""Series-reservoir damping scenarios; controlled AC comparison, not qualification."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 if c['reservoir']!='mim2048':continue
 for resistance in (.5,2,10,50):
  name=c['name']+f'_r{resistance:g}';src=B/(c['name']+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
  old='XRES OUT 0 pt_ref_reservoir_2048';assert d.count(old)==1
  d=d.replace(old,f'RDAMP OUT RES {resistance}\nXRES RES 0 pt_ref_reservoir_2048').replace(f'/work/{c["name"]}.dat',f'/work/{name}.dat')
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  rows.append(dict(name=name,baseline_name=c['name'],rail=c['rail'],dc_load_a=c['dc_load_a'],resistance_ohm=resistance,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log')}))
(O/'result.json').write_text(json.dumps(dict(status='reservoir_damping_AC_unverified',cases=rows,source_sha256=base['source_sha256']),indent=2)+'\n');print('Completed 24 damping scenarios.')
