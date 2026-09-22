"""Integrate a previously measured reference compensation candidate into ADC."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path(p) for p in base['source_sha256']]+[Path('/screen/reference')/s for s in ('adc_reference_pair_tuned.spice','buffer_scaled_tune.spice','buffer_complement_tune.spice')]
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');sources=sorted(set(sources+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'))));before={str(p):sha(p) for p in sources};rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=[c['name'] for c in base['cases']],change='Reference compensation only: actual CC8pF/R500ohm per S4 amplifier; same PDK reservoirs and ADC',scope='Two nominal opposite-history streams; target/bias/compensation components ideal'),indent=2)+'\n')
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];original=src.read_text()
 assert original.count('/screen/reference/adc_reference_pair.spice')==1
 d=original.replace('/screen/reference/adc_reference_pair.spice','/screen/reference/adc_reference_pair_tuned.spice').replace(' pt_adc_reference_pair\n',' pt_adc_reference_pair_tuned\n')
 assert d.replace('/screen/reference/adc_reference_pair_tuned.spice','/screen/reference/adc_reference_pair.spice').replace(' pt_adc_reference_pair_tuned\n',' pt_adc_reference_pair\n')==original
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=1800);code=r.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 rows.append(dict(name=name,corner=c['corner'],first_sign=c['first_sign'],returncode=code,timed_out=timeout,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');assert before==after
