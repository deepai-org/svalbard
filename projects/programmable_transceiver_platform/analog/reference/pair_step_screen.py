"""Bipolar1mA load pulse on retained actual pair/reservoirs; no circuit change."""
import hashlib,json,subprocess,time
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(parent_prefix='baseline_', *, entrypoint=None):
 prior=json.loads((B/'result.json').read_text());rows=[]
 for rail,node in [('h','OH'),('l','OL')]:
  parent=B/(parent_prefix+rail+'.spice');rec=next(x for x in prior['cases'] if x['name']==parent_prefix+rail);assert sha(parent)==rec['artifacts_sha256']['.spice']
  before=dict(rec['sources_before']);assert before==rec['sources_after']
  for n,h in before.items():assert sha(Path(n))==h
  before[str(Path(__file__))]=sha(Path(__file__))
  if entrypoint is not None:before[str(Path(entrypoint))]=sha(Path(entrypoint))
  body=parent.read_text().split('.control')[0];old=f'ILOAD {node} 0 DC 0 AC 1';assert body.count(old)==1
  for sign in (-1,1):
   name=f'{rail}_{sign}';stim=f'ILOAD {node} 0 PWL(0n 0 20n 0 20.1n {sign*.001} 30n {sign*.001} 30.1n 0 100n 0)'
   d=body.replace(old,stim)+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 5p 100n 0 5p
wrdata /work/{name}.dat v(OH) v(OL) i(VDD) v(XDUT.XHIGH.X) v(XDUT.XLOW.X)
.endc
.end
'''
   p=O/(name+'.spice');p.write_text(d);h=sha(p);start=time.monotonic()
   with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
   after={n:sha(Path(n)) for n in before};assert after==before and sha(p)==h
   rows.append(dict(name=name,rail=rail,sign=sign,returncode=q.returncode,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,parent_sha256=sha(parent),artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}));print(name,q.returncode,flush=True)
 (O/'result.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n')

if __name__=='__main__':main()
