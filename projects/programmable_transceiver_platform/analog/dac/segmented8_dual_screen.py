"""Complementary Q/QB interface comparison; unchanged capture fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');raw=json.loads((B/'result.json').read_text());base_manifest=json.loads((B/'manifest.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path(p) for p in raw['source_sha256_before']]+[Path('/screen/dac/segmented8_dual.spice')];before={str(p):sha(p) for p in sources}
extra=[f'v(XD.RLB{i})' for i in range(4)]+[f'v(XD.RHB{k})' for k in range(1,16)]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=['c32_skew-0.2','c32_skew0'],extra_vectors=extra,baseline_manifest=base_manifest),indent=2)+'\n');rows=[]
for name in ['c32_skew-0.2','c32_skew0']:
 src=B/(name+'.spice');c=next(c for c in raw['cases'] if c['name']==name);assert sha(src)==c['artifacts_sha256']['.spice']
 original=src.read_text();d=original.replace('segmented8_registered.spice','segmented8_dual.spice').replace('pt_dac_segmented8_registered','pt_dac_segmented8_dual').replace('\n.endc',' '+' '.join(extra)+'\n.endc')
 assert d.replace('segmented8_dual.spice','segmented8_registered.spice').replace('pt_dac_segmented8_dual','pt_dac_segmented8_registered').replace(' '+' '.join(extra)+'\n.endc','\n.endc')==original
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=r.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 rows.append(dict(name=name,returncode=code,timed_out=timeout,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');assert before==after
