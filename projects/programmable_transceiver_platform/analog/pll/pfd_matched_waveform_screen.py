"""Reduced failing PFD fixture: compare identical waveform representations."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'pwl_skew0.spice';base=src.read_text();rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');sources=[Path('/screen/pll')/n for n in ('pfd.spice','charge_pump.spice','loop_filter.spice')]+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,scope='800ns reproducer: original mixed sources versus bitwise-identical PWL input sources'),indent=2)+'\n')
ref=next(x for x in base.splitlines() if x.startswith('VREF '));old=next(x for x in base.splitlines() if x.startswith('VFB '));assert old=='VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
for variant in ('mixed','matched'):
 d=base.split('.control')[0]
 if variant=='matched':d=d.replace(old,ref.replace('VREF REF ','VFB FB ',1))
 d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REF) v(FB) v(UP) v(DN) v(CTRL) i(VSENSE)
tran 2p 800n 0 2p uic
wrdata /work/{variant}.dat v(REF) v(FB) v(UP) v(DN) v(CTRL) i(VSENSE)
.endc
.end
'''
 (O/(variant+'.spice')).write_text(d)
 with (O/(variant+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(variant+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=300)
 rows.append(dict(name=variant,returncode=r.returncode,artifacts_sha256={s:sha(O/(variant+s)) for s in ('.spice','.log','.dat') if (O/(variant+s)).exists()}));(O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(variant,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(status='matched_reference_reproducer_unverified',cases=rows,baseline_deck_sha256=sha(src),source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
