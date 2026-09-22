"""Closed-loop loaded AC response at three input operating points; not return ratio."""
import argparse,hashlib,json,re,subprocess
ap=argparse.ArgumentParser();ap.add_argument("--damping",action="store_true");args=ap.parse_args()
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
assert r['source_sha256_before']==r['source_sha256_after']
before=r['source_sha256_before'].copy()
for path,h in before.items():assert sha(Path(path))==h
before[str(Path(__file__))]=sha(Path(__file__))
assert sha(B/'loaded.spice')==r['artifacts_sha256']['.spice'];base=(B/'loaded.spice').read_text();rows=[]
for name,p,n in [('negative',.87,1.27),('center',1.07,1.07),('positive',1.27,.87)]:
 changes={next(x for x in base.splitlines() if x.startswith('VIP ')):f'VIP SP 0 DC {p} AC .5',next(x for x in base.splitlines() if x.startswith('VIN ')):f'VIN SN 0 DC {n} AC .5 180'}
 d=base
 for old,new in changes.items():d=d.replace(old,new)
 control=base[base.index('.control'):base.index('.endc')+len('.endc')]
 replacement=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac dec 100 1k 10G
let dr = real(v(IP)-v(IN))
let di = imag(v(IP)-v(IN))
let pr = real(v(HP)-v(HN))
let plate_im = imag(v(HP)-v(HN))
wrdata /work/{name}.dat dr di pr plate_im
.endc'''
 d=d.replace(control,replacement)
 rev=d.replace(replacement,control)
 for old,new in changes.items():rev=rev.replace(new,old)
 assert rev==base
 if args.damping:
  include=".include /screen/adc/sample_driver_headroom.spice"
  cell=Path("/screen/adc/sample_driver_headroom.spice").read_text()
  assert cell.count("RC X Z 100")==1
  changed=cell.replace("RC X Z 100","RC X Z 1k")
  original=d;d=d.replace(include,changed)
  assert d.replace(changed,include)==original
 path=O/(name+'.spice');path.write_text(d);h=sha(path)
 with (O/(name+'.log')).open('w') as log:run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 assert sha(path)==h
 rows.append(dict(name=name,source_voltages_v=[p,n],returncode=run.returncode,exact_reversal=True,compensation_resistor_ohm=1000 if args.damping else 100,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,baseline_deck_sha256=sha(B/'loaded.spice'),source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
print('AC cases finished',len(rows))
