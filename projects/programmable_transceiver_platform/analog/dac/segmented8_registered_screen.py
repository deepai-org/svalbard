"""Actual post-decode registers, conservative fixed capture interval diagnostic."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');old=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path(p) for p in old['source_sha256_before']]+[Path('/screen/dac/segmented8_registered.spice'),Path('/screen/pll/pfd.spice')];before={str(p):sha(p) for p in sources}
rows=[];extra=['v(XD.CK)','i(VCLK)']+[f'v(XD.RL{i})' for i in range(4)]+[f'v(XD.RH{k})' for k in range(1,16)]
manifest=dict(source_sha256_before=before,planned_cases=['c32_skew-0.2','c32_skew0'],extra_vectors=extra,clock_fixture='PULSE first6ns,period25ns,width5ns,100ps edges; reset release2ns',scope='Fixed capture opportunity ~1ns after nominal command onset; not setup/hold qualification')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name in manifest['planned_cases']:
 src=B/(name+'.spice');c=next(c for c in old['cases'] if c['name']==name);assert sha(src)==c['artifacts_sha256']['.spice']
 d=src.read_text().replace('/screen/dac/segmented8.spice','/screen/dac/segmented8_registered.spice')
 d=d.replace('XD OP ON BN VDRV 0 D0','XD OP ON BN VDRV 0 CLK RN D0').replace(' pt_dac_segmented8\n',' pt_dac_segmented8_registered\n')
 d=d.replace('.control','.include /screen/pll/pfd.spice\nVCLK CLK 0 PULSE(0 3.3 6n 100p 100p 5n 25n)\nVRN RN 0 PWL(0 0 2n 0 2.1n 3.3)\n.control')
 d=d.replace('\n.endc',' '+' '.join(extra)+'\n.endc')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=r.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 rows.append(dict(name=name,returncode=code,timed_out=timeout,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');assert before==after
