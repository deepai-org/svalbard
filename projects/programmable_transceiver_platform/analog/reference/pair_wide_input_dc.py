"""Small target perturbations of actual tuned reference pair, zero external DC load."""
import json
from pathlib import Path
from pair_dc_fixture import body, sha, source_hashes, device_probes, sweep_targets
O=Path('/work')
paths=source_hashes(body,O);paths[str(Path(__file__))]=sha(Path(__file__));rows=[]
pair=Path('/screen/reference/adc_reference_pair_tuned.spice').read_text()
expanded=pair
changes=[]
for filename in ('buffer_scaled_tune.spice','buffer_complement_tune.spice'):
 p=Path('/screen/reference')/filename;cell=p.read_text();changed=cell
 for line in cell.splitlines():
  if filename == 'buffer_complement_tune.spice' and line.startswith(('XIP ','XIN ')):
   assert 'w=8u l=.5u' in line
   new=line.replace('w=8u l=.5u','w=16u l=.5u');changed=changed.replace(line,new);changes.append((line,new))
 assert expanded.count('.include /screen/reference/'+filename)==1
 expanded=expanded.replace('.include /screen/reference/'+filename,changed)
assert len(changes)==2
body=body.replace('.include /screen/reference/adc_reference_pair_tuned.spice',expanded)
(O/'change-manifest.json').write_text(json.dumps(dict(changes=changes,scope='Only high-reference input-pair widths doubled; lengths, multiplicities, output stage, biases and compensation retained.'),indent=2)+'\n')
probes=device_probes()
rows=sweep_targets(body,probes,O)
assert paths=={n:sha(Path(n)) for n in paths}
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=paths,sources_after=paths),indent=2)+'\n');print([(r['name'],r['returncode']) for r in rows])
