"""Controlled larger PDK reservoir substitution in actual-driver ADC."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
 old='CHR VH 0 10p\nCLR VL 0 10p\n';new='.include /screen/reference/reservoir_mim.spice\nXHR VH 0 pt_ref_reservoir_2048\nXLR VL 0 pt_ref_reservoir_2048\n'
 assert d.count(old)==1;d=d.replace(old,new)
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 rows.append(dict(name=name,corner=c['corner'],first_sign=c['first_sign'],returncode=r.returncode,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}));print(name,r.returncode,flush=True)
source=base['source_sha256'].copy();p=Path('/screen/reference/reservoir_mim.spice');source[str(p)]=sha(p)
(O/'result.json').write_text(json.dumps(dict(status='larger_PDK_reservoir_connected_unverified',cases=rows,source_sha256=source,limitations=['2048 explicit PDK units per reference reservoir; conditional M4-M5 process option.', 'Nominal MIM only; driver compensation, target/bias and separate supply still ideal.', 'Finite selected streams; no noise/mismatch/stability/startup qualification.']),indent=2)+'\n')
