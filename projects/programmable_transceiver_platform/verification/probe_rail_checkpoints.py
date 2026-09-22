"""Preserve intermediate quiet-input rail traces before a bounded timeout."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from probe_rail_startup import probe
from run_gpio_transient import PAD

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    rows=list(pool.map(lambda mode:probe(mode,checkpoints=True),('ideal','supply_only','return_only','both')))
report={'scope':'12 ns quiet-input diagnostic with intermediate snapshots; no communication verdict',
        'results':rows,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                      (Path(__file__),Path('/src/verification/probe_rail_startup.py'),PAD)},
        'assumptions':['Checkpoints at 1,2,4,8,12 ns preserve state via stop/resume.',
                       'Default integration, 10 ps maximum step, 60 second per-case limit.',
                       'No input switching; same selected R/L as pass 13, not qualified package bounds.']}
Path('/work/rail-checkpoints.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
