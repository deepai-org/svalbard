"""Controlled internal Miller RC sweep with the existing PDK reservoir."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 if c['reservoir']!='mim2048':continue
 for cc in (.5,1,2,4):
  for rz in (100,500,2000):
   name=c['name']+f'_cc{cc:g}_rz{rz}';src=B/(c['name']+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
   for kind in ('scaled','complement'):
    d=d.replace(f'buffer_{kind}.spice',f'buffer_{kind}_tune.spice').replace(f'pt_reference_buffer_{kind} S=4',f'pt_reference_buffer_{kind}_tune S=4 CC={cc}p RZ={rz}')
   d=d.replace(f'/work/{c["name"]}.dat',f'/work/{name}.dat')
   (O/(name+'.spice')).write_text(d)
   with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
   rows.append(dict(name=name,baseline_name=c['name'],rail=c['rail'],dc_load_a=c['dc_load_a'],cc_unit_pf=cc,rz_unit_ohm=rz,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log')}))
 print('Completed '+c['name'],flush=True)
sources=base['source_sha256'].copy()
for kind in ('scaled','complement'):
 p=Path('/screen/reference')/f'buffer_{kind}_tune.spice';sources[str(p)]=sha(p)
(O/'result.json').write_text(json.dumps(dict(status='internal_compensation_AC_unverified',cases=rows,source_sha256=sources),indent=2)+'\n')
