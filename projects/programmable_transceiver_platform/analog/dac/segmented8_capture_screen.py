"""Signed capture timing scenarios around existing registered DAC fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'c32_skew0.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==next(c for c in base['cases'] if c['name']=='c32_skew0')['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};rows=[]
manifest=dict(source_sha256_before=before,baseline_deck_sha256=sha(src),capture_offsets_ns=[-.8,-.5,.5],scope='Nominal code127/128,zero command skew,32-unit output load; only external clock phase changes')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for offset in manifest['capture_offsets_ns']:
 name=f'capture{offset:g}';old='VCLK CLK 0 PULSE(0 3.3 6n 100p 100p 5n 25n)';new=f'VCLK CLK 0 PULSE(0 3.3 {6+offset:g}n 100p 100p 5n 25n)'
 original=src.read_text();assert original.count(old)==1
 d=original.replace(old,new).replace('/work/c32_skew0.dat',f'/work/{name}.dat');assert d.replace(new,old).replace(f'/work/{name}.dat','/work/c32_skew0.dat')==original
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=r.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 rows.append(dict(name=name,capture_offset_ns=offset,returncode=code,timed_out=timeout,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');assert before==after
