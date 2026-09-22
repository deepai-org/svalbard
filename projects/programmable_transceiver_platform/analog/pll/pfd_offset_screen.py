"""Signed feedback-source offsets; retain the failing buffered PWL reference."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work'); B=Path('/baseline/pwl.spice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
sources=[B]+[Path('/screen/pll')/n for n in ('pfd.spice','charge_pump.spice','loop_filter.spice','reference_input_buffer.spice')]+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'))
before={str(p):sha(p) for p in sources}; rows=[]
manifest=dict(source_sha256_before=before,offsets_ps=[-10,10],scope='800ns forced feedback; diagnostic source-event offsets, not autonomous acquisition')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for offset in manifest['offsets_ps']:
 name=f'offset{offset}'
 original=B.read_text()
 old='VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
 new=f'VFB FB 0 PULSE(0 3.3 {100000+offset}p 100p 100p 25.5n 51.2n)'
 assert original.count(old)==1
 deck=original.replace(old,new).replace('/work/pwl.dat',f'/work/{name}.dat')
 assert deck.replace(new,old).replace(f'/work/{name}.dat','/work/pwl.dat')==original
 path=O/(name+'.spice');path.write_text(deck); pre=sha(path)
 with (O/(name+'.log')).open('w') as log:
  try:
   result=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
   code=result.returncode;timeout=False
  except subprocess.TimeoutExpired:
   code=None;timeout=True
 assert sha(path)==pre
 rows.append(dict(name=name,offset_ps=offset,returncode=code,timed_out=timeout,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after,unchanged_sources=before==after),indent=2)+'\n')
assert before==after
