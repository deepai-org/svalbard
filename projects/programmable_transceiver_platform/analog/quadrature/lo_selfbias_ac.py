"""Small-signal self-bias/coupling diagnostic; not periodically switching operation."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
body='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/lo_buffer.spice
.include /screen/quadrature/lo_final_stage.spice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.include /screen/reference/reservoir_mim.spice
.temp 27
.options reltol=1e-5 vntol=1e-8 abstol=1e-14
VDD VDD 0 3.3
VIN SIG 0 DC 2.24 AC 1
XC SIG IN pt_ref_reservoir_4
RFB IN XB.MID 100k
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
for name,start,stop,step in [('ac',0,0,0)]:
 d=body+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
op
wrdata /work/op.dat v(IN) v(XB.MID) v(PRE) v(OUT) i(VDD)
ac dec 40 1k 10G
let ir=real(v(IN))
let ii=imag(v(IN))
let mr=real(v(XB.MID))
let mi=imag(v(XB.MID))
wrdata /work/{name}.dat ir ii mr mi
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 rows.append(dict(name=name,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
after={n:sha(Path(n)) for n in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=before,sources_after=after,op_sha256=sha(O/'op.dat')),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
