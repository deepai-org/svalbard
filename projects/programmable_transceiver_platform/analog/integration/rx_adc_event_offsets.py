"""Replay prepared signed edge perturbations; preserve actual loaded receiver."""
import hashlib,json,subprocess,time
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(source_output='/work/loaded/connected.dat', *, entrypoint=None):
 O=Path('/work');B=Path('/baseline');V=Path('/variants')
 r=json.loads((B/'result.json').read_text());m=json.loads((V/'manifest.json').read_text());assert sha(B/'connected.spice')==m['parent_deck_sha256']
 before=dict(r['sources_before']);assert before==r['sources_after']
 for n,h in before.items():assert sha(Path(n))==h,n
 before[str(Path(__file__))]=sha(Path(__file__))
 if entrypoint is not None:before[str(Path(entrypoint))]=sha(Path(entrypoint))
 for case in m['cases']:
  name=case['case'];out=O/name;out.mkdir(exist_ok=False);src=V/(name+'.spice');assert sha(src)==case['deck_sha256']
  d=src.read_text().replace(source_output,f'/work/{name}/connected.dat');p=out/'connected.spice';p.write_text(d);h=sha(p)
  (out/'manifest.json').write_text(json.dumps(dict(preparation=case,deck_sha256=h,sources_before=before,requested_horizon_ns=610),indent=2)+'\n');start=time.monotonic()
  with (out/'connected.log').open('w') as log:
   try:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=10800);code=q.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
  after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==h
  (out/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={e:sha(out/('connected'+e)) for e in ('.spice','.log','.dat') if (out/('connected'+e)).exists()}),indent=2)+'\n');print(name,code,timeout,flush=True)

if __name__ == "__main__":
 main()
