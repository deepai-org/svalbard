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
 if filename=='buffer_complement_tune.spice':
  ncell=Path('/screen/reference/buffer_scaled_tune.spice').read_text()
  for instance in ('XIP','XIN','XT','XMP','XMN'):
   old=next(l for l in cell.splitlines() if l.startswith(instance+' '))
   new=next(l for l in ncell.splitlines() if l.startswith(instance+' '))
   changed=changed.replace(old,new);changes.append((old,new))
 assert expanded.count('.include /screen/reference/'+filename)==1
 expanded=expanded.replace('.include /screen/reference/'+filename,changed)
assert len(changes)==5
body=body.replace('.include /screen/reference/adc_reference_pair_tuned.spice',expanded)
(O/'change-manifest.json').write_text(json.dumps(dict(changes=changes,scope='High first-stage five devices replaced with retained NMOS-input topology; high PMOS output and low stage unchanged.'),indent=2)+'\n')
probes=device_probes()
rows=sweep_targets(body,probes,O)
assert paths=={n:sha(Path(n)) for n in paths}
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=paths,sources_after=paths),indent=2)+'\n');print([(r['name'],r['returncode']) for r in rows])
