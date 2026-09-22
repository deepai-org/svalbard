"""Run the prepared loaded receiver replay, preserving failure artifacts."""
import hashlib,json,re,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/prepared')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
paths={Path(__file__)}
def scan(s,parent):
 for l in s.splitlines():
  z=re.match(r'\s*\.(?:include|lib)\s+(\S+)',l,re.I)
  if not z:continue
  p=Path(z[1].strip(chr(34)+chr(39)));p=p if p.is_absolute() else parent/p
  if not p.is_file():assert l.lower().lstrip().startswith('.lib ') and len(l.split())==2;continue
  p=p.resolve()
  if p not in paths:paths.add(p);scan(p.read_text(),p.parent)
s=(B/'latest.spice').read_text();scan(s,B);before={str(p):sha(p) for p in paths}
for n,h in before.items():
 if n in m['source_provenance']:assert m['source_provenance'][n]==h
p=O/'latest.spice';p.write_text(s);start=time.monotonic()
(O/'manifest.json').write_text(json.dumps(dict(preparation_sha256=sha(B/'manifest.json'),sources_before=before,deck_sha256=sha(p)),indent=2)+'\n')
with (O/'latest.log').open('w') as f:
 try:q=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=14400);code=q.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={n:sha(Path(n)) for n in before};assert after==before
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={e:sha(O/('latest'+e)) for e in ('.spice','.log','.dat') if (O/('latest'+e)).exists()}),indent=2)+'\n');print(code,timeout)
