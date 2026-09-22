"""LO source impedance scenarios, preserving actual downstream transistor circuits."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,resistance_ohm=[50,500],scope='Fullscale only;50/500ohm per ideal source into existing buffers. Scenarios, not measured oscillator output impedance.'),indent=2)+'\n');rows=[]
for variant in ('nmos','tg'):
 baseline=variant+'_c255';src=B/(baseline+'.spice');bc=next(c for c in base['cases'] if c['name']==baseline);assert sha(src)==bc['artifacts_sha256']['.spice']
 for resistance in (50,500):
  name=f'{variant}_r{resistance}';add=f'RSP LOSRC LOIN {resistance}\nRSN LOBSRC LOBIN {resistance}\n'
  d=src.read_text().replace('VLO LOIN 0 PULSE','VLO LOSRC 0 PULSE').replace('VLOB LOBIN 0 PULSE','VLOB LOBSRC 0 PULSE').replace('.control',add+'.control').replace('/work/'+baseline+'.dat','/work/'+name+'.dat')
  p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
  with (O/(name+'.log')).open('w') as f:
   try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=240);rc=r.returncode;timeout=False
   except subprocess.TimeoutExpired:rc=None;timeout=True
  assert sha(p)==pre
  rows.append(dict(name=name,baseline=baseline,resistance_ohm=resistance,returncode=rc,timed_out=timeout,baseline_deck_sha256=sha(src),deck_sha256_before=pre,elapsed_seconds=time.monotonic()-start,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
