"""Compare linear solvers; keep physical deck and integration settings fixed."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from probe_rail_startup import probe
from run_gpio_transient import PAD

matrix=[(mode,solver) for mode in ('ideal','both') for solver in ('sparse','klu')]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    rows=list(pool.map(lambda c:probe(c[0],checkpoints=True,solver=c[1]),matrix))
checks={}
for mode in ('ideal','both'):
    decks=[]
    for solver in ('sparse','klu'):
        path=Path('/work')/(mode+'_'+solver)
        decks.append((path/'tb.spice').read_text().replace(str(path),'/work/CASE'))
    checks[mode]=decks[0]==decks[1]
if not all(checks.values()):raise ValueError('physical or integration deck changed between solvers')
report={'scope':'quiet-rail numerical solver comparison; no switching qualification',
        'normalized_decks_equal':checks,'results':rows,
        'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        (Path(__file__),Path('/src/verification/probe_rail_startup.py'),
                         Path('/src/verification/run_gpio_transient.py'),PAD)}}
Path('/work/rail-solvers.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'normalized_decks_equal':checks,'cases':[{'case':r['case'],'solver_observed':r['solver_observed'],
                   'execution_status':r['execution_status'],'last_saved_time_s':r.get('last_time_s')} for r in rows]},indent=2))
