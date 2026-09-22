"""Small target perturbations of actual tuned reference pair, zero external DC load."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
body='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/reference/adc_reference_pair_tuned.spice
.temp 27
VDD VDD 0 3.3
VH HIGH 0 2.15
VL LOW 0 1.15
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XDUT HIGH LOW OH OL BN BP VDD 0 pt_adc_reference_pair_tuned
'''
paths={}
def scan(text,parent):
 for line in text.splitlines():
  m=re.match(r'\s*\.(?:include|lib)\s+(\S+)',line,re.I)
  if not m:continue
  q=Path(m[1].strip(chr(34)+chr(39)));q=q if q.is_absolute() else parent/q
  if not q.is_file():assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
  q=q.resolve()
  if str(q) not in paths:paths[str(q)]=sha(q);scan(q.read_text(),q.parent)
scan(body,O);paths[str(Path(__file__))]=sha(Path(__file__));rows=[]
pair=Path('/screen/reference/adc_reference_pair_tuned.spice').read_text()
expanded=pair
changes=[]
for filename in ('buffer_scaled_tune.spice','buffer_complement_tune.spice'):
 p=Path('/screen/reference')/filename;cell=p.read_text();changed=cell
 for line in cell.splitlines():
  if filename == 'buffer_complement_tune.spice' and line.startswith('XT '):
   assert 'm={16*S}' in line
   new=line.replace('m={16*S}','m={8*S}');changed=changed.replace(line,new);changes.append((line,new))
 assert expanded.count('.include /screen/reference/'+filename)==1
 expanded=expanded.replace('.include /screen/reference/'+filename,changed)
assert len(changes)==1
body=body.replace('.include /screen/reference/adc_reference_pair_tuned.spice',expanded)
(O/'change-manifest.json').write_text(json.dumps(dict(changes=changes,scope='Only high-reference tail multiplicity halved; input and output geometry, biases and compensation retained.'),indent=2)+'\n')
probes=[f'v(XDUT.{stage}.{node})' for stage in ('XHIGH','XLOW') for node in ('A','X','T')]
probes += [f'@m.xdut.{stage}.{dev}.m0[{q}]' for stage in ('xhigh','xlow') for dev in ('xip','xin','xt','xmp','xmn','xout','xload') for q in ('vds','vdsat','id','gm','gds')]
for name,target in [('VH',2.15),('VL',1.15)]:
 d='* Paired reference target response\n'+body+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save all {' '.join(probes)}
dc {name} {target-.02:.6f} {target+.02:.6f} .001
wrdata /work/{name}.dat v(HIGH) v(LOW) v(OH) v(OL) v(BN) v(BP) i(VDD) {' '.join(probes)}
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
 assert sha(p)==h;rows.append(dict(name=name,target_v=target,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}))
assert paths=={n:sha(Path(n)) for n in paths}
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=paths,sources_after=paths),indent=2)+'\n');print([(r['name'],r['returncode']) for r in rows])
