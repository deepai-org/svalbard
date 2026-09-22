"""Actual reference input buffer in the reduced PFD numerical diagnostic."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');sources=[Path('/screen/pll')/n for n in ('pfd.spice','charge_pump.spice','loop_filter.spice','reference_input_buffer.spice')]+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=['pulse','pwl'],scope='800ns, actual reference buffer, forced equal-frequency ideal feedback; not autonomous lock'),indent=2)+'\n')
for kind in ('pulse','pwl'):
 src=B/f'{kind}_skew0.spice';d=src.read_text().split('.control')[0]
 assert d.count('VREF REF 0 ')==1
 d=d.replace('VREF REF 0 ','VREF REFRAW 0 ')
 d+='.include /screen/pll/reference_input_buffer.spice\nXREFBUF REFRAW REF VDIV 0 pt_reference_input_buffer\n'
 d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REFRAW) v(REF) v(FB) v(UP) v(DN) v(CTRL) i(VSENSE)
tran 2p 800n 0 2p uic
wrdata /work/{kind}.dat v(REFRAW) v(REF) v(FB) v(UP) v(DN) v(CTRL) i(VSENSE)
.endc
.end
'''
 (O/(kind+'.spice')).write_text(d)
 with (O/(kind+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(kind+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=300)
 rows.append(dict(name=kind,returncode=r.returncode,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(kind+s)) for s in ('.spice','.dat','.log') if (O/(kind+s)).exists()}));(O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(kind,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(status='buffered_reference_diagnostic_unverified',cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
