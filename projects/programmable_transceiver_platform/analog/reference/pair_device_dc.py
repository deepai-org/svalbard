"""Small target perturbations of actual tuned reference pair, zero external DC load."""
import json
from pathlib import Path
from pair_dc_fixture import body, sha, source_hashes, device_probes, sweep_targets
O=Path('/work')
paths=source_hashes(body,O);paths[str(Path(__file__))]=sha(Path(__file__));rows=[]
probes=device_probes()
rows=sweep_targets(body,probes,O)
assert paths=={n:sha(Path(n)) for n in paths}
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=paths,sources_after=paths),indent=2)+'\n');print([(r['name'],r['returncode']) for r in rows])
