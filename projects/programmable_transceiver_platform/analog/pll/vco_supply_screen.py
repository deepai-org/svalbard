"""Loaded open-loop ring supply sensitivity; deterministic diagnostic only."""
import hashlib,json,re,subprocess,sys
RIPPLE="--ripple" in sys.argv
FINE="--fine" in sys.argv
assert not FINE or RIPPLE
from pathlib import Path
O=Path('/work');B=Path('/baseline/v1.08.spice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B.parent/'result.json').read_text());c=next(c for c in r['cases'] if c['control_v']==1.08)
assert sha(B)==c['artifacts_sha256']['.spice']
original=B.read_text();assert original.count('VPLL PLLVDD 0 3.3')==1
paths={B,Path(__file__).with_name('spice_dependencies.py')}
from spice_dependencies import dependencies

dependencies(original,B.parent,paths)
before={str(p):sha(p) for p in sorted(paths)}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,supply_v=[3.29,3.3,3.31] if not RIPPLE else [3.3,3.3],ripple_mode=RIPPLE,max_step_ps=1 if FINE else 2,ripple_frequency_hz=50e6 if RIPPLE else None,ripple_peak_v=.01 if RIPPLE else None,baseline_deck_sha256=sha(B),scope='Seeded prebiased ring with actual RF/divider/PFD loading; fixed ideal control and regen, no closed PLL or intrinsic noise'),indent=2)+'\n')
rows=[]
for name,supply in ([("quiet",3.3),("ripple",3.3)] if RIPPLE else [(f"v{x:g}",x) for x in (3.29,3.3,3.31)]):
 d=original.replace('VPLL PLLVDD 0 3.3',f'VPLL PLLVDD 0 {supply}').replace('/work/v1.08.dat',f'/work/{name}.dat')
 if RIPPLE:
  assert 'tran 2p 41n 0 2p uic' in d
  d=d.replace('tran 2p 41n 0 2p uic','tran 2p 201n 0 2p uic')
  if name=='ripple':d=d.replace('VPLL PLLVDD 0 3.3','VPLL PLLVDD 0 SIN(3.3 .01 50meg 20n)')
 if FINE:d=d.replace('tran 2p 201n 0 2p uic','tran 1p 201n 0 1p uic')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:
   result=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600 if FINE else 300);code=result.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,supply_v=supply,returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sorted(paths)};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
