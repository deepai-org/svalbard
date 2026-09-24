"""Run the prepared loaded receiver replay, preserving failure artifacts."""
import hashlib,json,re,subprocess,time,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spice_sources import collect_sources, __file__ as source_scanner_file
O=Path('/work');B=Path('/prepared')
name=sys.argv[1];assert name in ['baseline','replay']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
paths={Path(__file__)}
paths.add(Path(source_scanner_file))
s=(B/(name+'.spice')).read_text();collect_sources(s, B, paths, include_inc=False);before={str(p):sha(p) for p in paths}
for n,h in before.items():
 if n in m.get('source_provenance',{}):assert m['source_provenance'][n]==h
p=O/(name+'.spice');p.write_text(s);start=time.monotonic()
(O/'manifest.json').write_text(json.dumps(dict(preparation_sha256=sha(B/'manifest.json'),sources_before=before,deck_sha256=sha(p)),indent=2)+'\n')
with (O/(name+'.log')).open('w') as f:
 try:q=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=7200);code=q.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={n:sha(Path(n)) for n in before};assert after==before
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}),indent=2)+'\n');print(code,timeout)
