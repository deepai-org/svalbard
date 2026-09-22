"""Double output stage only; matched signed reference pulse comparison."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path(p) for p in base['source_sha256_before']]+[Path('/screen/reference')/f'buffer_{kind}_output2.spice' for kind in ('scaled','complement')]
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');sources=sorted(set(sources+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'))));before={str(p):sha(p) for p in sources};rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=[c['name'] for c in base['cases']],scope='Output/load multiplicity2x; same input stage, compensation, reservoir and signed2mA pulse'),indent=2)+'\n')
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];original=src.read_text();d=original
 for kind in ('scaled','complement'):d=d.replace(f'buffer_{kind}_tune.spice',f'buffer_{kind}_output2.spice').replace(f'pt_reference_buffer_{kind}_tune',f'pt_reference_buffer_{kind}_output2')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
 rows.append(dict(name=name,rail=c['rail'],load_ma=c['load_ma'],returncode=r.returncode,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
