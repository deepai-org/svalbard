"""Small target perturbations of actual tuned reference pair, zero external DC load."""
import json,subprocess
from pathlib import Path
from pair_dc_fixture import body, sha, source_hashes
O=Path('/work')
paths=source_hashes(body,O);paths[str(Path(__file__))]=sha(Path(__file__));rows=[]
for name,target in [('VH',2.15),('VL',1.15)]:
 d='* Paired reference target response\n'+body+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
dc {name} {target-.02:.6f} {target+.02:.6f} .001
wrdata /work/{name}.dat v(HIGH) v(LOW) v(OH) v(OL) v(BN) v(BP) i(VDD)
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
 assert sha(p)==h;rows.append(dict(name=name,target_v=target,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}))
assert paths=={n:sha(Path(n)) for n in paths}
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=paths,sources_after=paths),indent=2)+'\n');print([(r['name'],r['returncode']) for r in rows])
