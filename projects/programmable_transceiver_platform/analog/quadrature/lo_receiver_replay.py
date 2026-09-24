"""Run the prepared loaded receiver replay, preserving failure artifacts."""
import hashlib,json,re,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/prepared')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def main(stem='replay', timeout_s=7200, *, entrypoint=None):
 deck_name=stem+'.spice';log_name=stem+'.log'
 m=json.loads((B/'manifest.json').read_text())
 for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
 paths={Path(__file__)}
 if entrypoint is not None:paths.add(Path(entrypoint))
 def scan(s,parent):
  for l in s.splitlines():
   z=re.match(r'\s*\.(?:include|lib)\s+(\S+)',l,re.I)
   if not z:continue
   p=Path(z[1].strip(chr(34)+chr(39)));p=p if p.is_absolute() else parent/p
   if not p.is_file():assert l.lower().lstrip().startswith('.lib ') and len(l.split())==2;continue
   p=p.resolve()
   if p not in paths:paths.add(p);scan(p.read_text(),p.parent)
 s=(B/deck_name).read_text();scan(s,B);before={str(p):sha(p) for p in paths}
 for n,h in before.items():
  if n in m['source_provenance']:assert m['source_provenance'][n]==h
 p=O/deck_name;p.write_text(s);start=time.monotonic()
 (O/'manifest.json').write_text(json.dumps(dict(preparation_sha256=sha(B/'manifest.json'),sources_before=before,deck_sha256=sha(p)),indent=2)+'\n')
 with (O/log_name).open('w') as f:
  try:q=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=timeout_s);code=q.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 after={n:sha(Path(n)) for n in before};assert after==before
 (O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={e:sha(O/(stem+e)) for e in ('.spice','.log','.dat') if (O/(stem+e)).exists()}),indent=2)+'\n');print(code,timeout)

if __name__=='__main__':main()
