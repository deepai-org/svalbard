"""Large-signal track-mode settling across MIM loads and compensation settings."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
 d=d.replace('VP GP 0 DC 1.65 AC .5','VP GP 0 PWL(0 1.45 20n 1.45 20.1n 1.85 60n 1.85 60.1n 1.45)')
 d=d.replace('VN GN 0 DC 1.65 AC -.5','VN GN 0 PWL(0 1.85 20n 1.85 20.1n 1.45 60n 1.45 60.1n 1.85)')
 d=d.split('.control')[0]+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 5p 100n 0 5p
wrdata /work/{name}.dat v(HP) v(HN) v(IP) v(IN) v(GP) v(GN) i(VDD)
.endc
.end
'''
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 rows.append(dict(name=name,corner=c['corner'],compensation_pf=c['compensation_pf'],baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log')}))
 print('Completed '+name,flush=True)
(O/'result.json').write_text(json.dumps(dict(status='isolated_track_large_signal_unverified',cases=rows,source_sha256=base['source_sha256'],limitations=base['limitations']+['0.8V differential input reversal, continuously tracking; no turnoff, CDAC trials or comparator.', 'Large-signal response alone does not establish return-ratio stability margins.']),indent=2)+'\n')
