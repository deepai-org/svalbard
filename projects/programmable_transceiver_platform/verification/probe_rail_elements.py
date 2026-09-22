"""Separate rail R/L and isolate native MOS capacitors; diagnostic reductions only."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from probe_rail_startup import probe
from run_gpio_transient import PAD, TECH

matrix=[('r',False),('l',False),('rl',True),('r',True)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    rows=list(pool.map(lambda c:probe('both',checkpoints=True,rail_elements=c[0],capacitor_only=c[1]),matrix))
report={'scope':'quiet-input diagnostic reductions, not physical pad qualification',
        'results':rows,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
               (Path(__file__),Path('/src/verification/probe_rail_startup.py'),Path('/src/verification/run_gpio_transient.py'),PAD,TECH/'sm141064.spice')},
        'assumptions':['R-only is 0.25 ohm per rail; L-only is 2 nH per rail; all controls unchanged.',
                       'Capacitor-only cases retain two native cap_nmos_06v0 instances per pad and remove all other pad devices.',
                       'The reduced diagnostic cannot substitute for the full pad or relax package requirements.']}
Path('/work/rail-elements.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([{'case':r['case'],'status':r['execution_status'],'last_time_s':r.get('last_time_s')} for r in rows],indent=2))
