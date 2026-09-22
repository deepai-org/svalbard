"""Move DAC termination and RF load bias together; unchanged switch geometry."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());src=B/'r50_lo1.spice';case=next(c for c in base['cases'] if c['name']=='r50_lo1')
assert sha(src)==case['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),scope='50ohm per leg, static LO high; move both ideal termination biases by +/-0.3V. Diagnostic scenarios, not an allocated operating range.'),indent=2)+'\n')
for name,term,cm in [('lower',1.85,1.59),('baseline',2.15,1.89),('upper',2.45,2.19)]:
 d=src.read_text().replace('VTERM TERM 0 2.15',f'VTERM TERM 0 {term}').replace('VCM CM 0 1.89',f'VCM CM 0 {cm}').replace('/work/r50_lo1.dat',f'/work/{name}.dat')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180)
 assert sha(p)==pre
 rows.append(dict(name=name,term_v=term,cm_v=cm,returncode=r.returncode,elapsed_seconds=time.monotonic()-start,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
