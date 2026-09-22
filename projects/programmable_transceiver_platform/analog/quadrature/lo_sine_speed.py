"""Ideal sinusoidal drive at observed swing scale; intrinsic chain diagnostic only."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
body='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/lo_buffer.spice
.include /screen/quadrature/lo_final_stage.spice
.temp 27
.options reltol=1e-5 vntol=1e-8 abstol=1e-14
VDD VDD 0 3.3
VIN IN 0 1.5
XB IN PRE VDD 0 pt_lo_buffer
XF PRE OUT VDD 0 pt_lo_final_stage
CL OUT 0 50f
'''
paths={Path(__file__)}
def scan(s,parent):
 for line in s.splitlines():
  m=re.match(r'\s*\.(?:include|lib)\s+(\S+)',line,re.I)
  if not m:continue
  p=Path(m[1].strip(chr(34)+chr(39)));p=p if p.is_absolute() else parent/p
  if not p.is_file():assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
  p=p.resolve()
  if p not in paths:paths.add(p);scan(p.read_text(),p.parent)
scan(body,O);before={str(p):sha(p) for p in paths};rows=[]
for name,start,stop,step in [('small',.095,0,0),('large',.108,0,0)]:
 d=body.replace('VIN IN 0 1.5',f'VIN IN 0 SIN(1.530318 {start} 2.5g)')+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 1p 100n 0 1p
wrdata /work/{name}.dat v(IN) v(XB.MID) v(PRE) v(OUT) i(VDD)
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 rows.append(dict(name=name,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
after={n:sha(Path(n)) for n in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=before,sources_after=after),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
