"""Sampler-release-only perturbation of completed full dual ADC candidate."""
import argparse,hashlib,json,re,subprocess
from decimal import Decimal
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--edge',choices=['early','late'],required=True);args=ap.parse_args()
B=Path('/baseline');O=Path('/work');delta=Decimal('-.1' if args.edge=='early' else '.1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
before=r['source_sha256_before'].copy()
for p,h in before.items():assert sha(Path(p))==h
before[str(Path(__file__))]=sha(Path(__file__))
assert sha(B/'frames.spice')==r['artifacts_sha256']['.spice'];base=(B/'frames.spice').read_text();d=base;changes={}
times={'70','70.1','120','120.1','170','170.1'}
for line in base.splitlines():
 if line.startswith(('VS ','VSB ')):
  new=re.sub(r'(?<![\d.])(\d+(?:\.\d+)?)n',lambda m:str(Decimal(m[1])+delta)+'n' if m[1] in times else m[0],line)
  assert new!=line;changes[line]=new;d=d.replace(line,new)
assert len(changes)==2
rev=d
for old,new in changes.items():rev=rev.replace(new,old)
assert rev==base
p=O/'frames.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(B/'frames.spice'),deck_sha256_before=h,source_sha256_before=before,changes=changes,edge=args.edge,offset_ns=float(delta),scope='Only both sampler release ramps shift; mask/conversion/reset/input schedules unchanged.'),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:run=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=run.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
