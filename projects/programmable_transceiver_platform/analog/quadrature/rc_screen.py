"""PDK passive quadrature AC diagnostic, explicit source/load assumptions."""
import hashlib,json,re,subprocess,sys
ASYM="--asymmetric" in sys.argv
BUFFERED="--buffered" in sys.argv
assert not (ASYM and BUFFERED)
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base='''* Differential source1V AC,25ohm per leg,ideal1.5V common mode
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.include /screen/quadrature/rc_split.spice
.temp 27
VC CM 0 1.5
VP SP 0 DC 1.5 AC .5
VN SN 0 DC 1.5 AC .5 180
RP SP P 25
RN SN N 25
XQ P N IP IN QP QN CM 0 pt_rc_quadrature
'''
if BUFFERED:
 base+='.include /screen/lo_buffer.spice\nVBUF VDD 0 3.3\n'
 for node in ('IP','IN','QP','QN'):
  base+=f'XC{node} {node} B{node} pt_ref_reservoir_4\nRFB{node} B{node} XB{node}.MID 100k\nXB{node} B{node} O{node} VDD 0 pt_lo_buffer\nCL{node} O{node} 0 50f\n'
paths=set()
def deps(text,parent):
 for line in text.splitlines():
  m=re.match(r'\s*\.(?:include|lib|inc)\s+(\S+)',line,re.I)
  if not m:continue
  p=Path(m[1].strip('"\''));p=p if p.is_absolute() else parent/p
  if not p.is_file():
   assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
  p=p.resolve()
  if p not in paths:paths.add(p);deps(p.read_text(),p.parent)
deps(base,O);before={str(p):sha(p) for p in sorted(paths)}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,asymmetric=ASYM,buffered=BUFFERED,loads_f=[0,25e-15,100e-15],source_ohm_per_leg=25,resistor_length_um=2),indent=2)+'\n')
rows=[]
for iload,qload in ([(25e-15,25e-15),(25e-15,100e-15),(100e-15,25e-15)] if ASYM else [(25e-15,25e-15)] if BUFFERED else [(x,x) for x in (0,25e-15,100e-15)]):
 load=iload
 name=f'i{iload*1e15:g}_q{qload*1e15:g}' if ASYM else f'load{load*1e15:g}'
 d=base+''.join(f'C{node} {node} CM {cap}\n' for node,cap in [('IP',iload),('IN',iload),('QP',qload),('QN',qload)] if cap)
 d+='''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac lin 41 2g 3g
let ir=real(v(IP)-v(IN))
let ii=imag(v(IP)-v(IN))
let qr=real(v(QP)-v(QN))
let qi=imag(v(QP)-v(QN))
'''+f'wrdata /work/{name}.dat ir ii qr qi\n.endc\n.end\n'
 if BUFFERED:
  d=d.replace('ac lin 41 2g 3g',f'op\nwrdata /work/{name}-bias.dat v(BIP) v(BIN) v(BQP) v(BQN) i(VBUF)\nac lin 41 2g 3g')
  d=d.replace(f'wrdata /work/{name}.dat ir ii qr qi',f'let bir=real(v(OIP)-v(OIN))\nlet bii=imag(v(OIP)-v(OIN))\nlet bqr=real(v(OQP)-v(OQN))\nlet bqi=imag(v(OQP)-v(OQN))\nwrdata /work/{name}.dat ir ii qr qi bir bii bqr bqi')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
 rows.append(dict(name=name,load_f=load,q_load_f=qload,returncode=r.returncode,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in (('.spice','.log','.dat','-bias.dat') if BUFFERED else ('.spice','.log','.dat')) if (O/(name+e)).exists()}))
after={str(p):sha(p) for p in sorted(paths)};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
