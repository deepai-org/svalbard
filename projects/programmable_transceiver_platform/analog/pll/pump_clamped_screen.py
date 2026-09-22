"""Actual PFD/pump with fixed output voltage; diagnostic source, not PLL repair."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
probes=' v(XCP.UPB) v(XCP.PS) v(XCP.NS) v(BPCP) v(BNCP) i(VCLAMP)'
rows=[]
for prior in r['cases']:
 name=prior['name'];src=B/(name+'.spice');assert sha(src)==prior['artifacts_sha256']['.spice']
 original=src.read_text();assert original.count('.control')==1
 d=original.replace('.control','VCLAMP CTRL 0 1.08\n.control')
 d='\n'.join(line+probes if line.startswith(('save ','wrdata ')) else line for line in d.splitlines())+'\n'
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,delay=prior['delay'],baseline_deck_sha256=sha(src),returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
