"""Resistor-only controlled transient candidate from completed loaded baseline."""
import argparse,hashlib,json,subprocess
ap=argparse.ArgumentParser();ap.add_argument("--resistor",choices=["1k","2k"],default="1k");args=ap.parse_args()
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
before=r['source_sha256_before'].copy()
for p,h in before.items():assert sha(Path(p))==h
before[str(Path(__file__))]=sha(Path(__file__))
assert sha(B/'loaded.spice')==r['artifacts_sha256']['.spice']
base=(B/'loaded.spice').read_text();cell=Path('/screen/adc/sample_driver_headroom.spice').read_text();include='.include /screen/adc/sample_driver_headroom.spice'
assert cell.count('RC X Z 100')==1 and base.count(include)==1
changed=cell.replace('RC X Z 100','RC X Z '+args.resistor);d=base.replace(include,changed);assert d.replace(changed,include)==base
p=O/'loaded.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=h,baseline_deck_sha256=sha(B/'loaded.spice'),exact_reversal=True,requested_horizon_ns=100,scope='Only driver compensation series resistor100ohm->'+args.resistor+'; all other circuit and transient parameters retained.'),indent=2)+'\n')
with (O/'loaded.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('loaded'+e)) for e in ('.spice','.log','.dat') if (O/('loaded'+e)).exists()}),indent=2)+'\n');print(code,timeout)
