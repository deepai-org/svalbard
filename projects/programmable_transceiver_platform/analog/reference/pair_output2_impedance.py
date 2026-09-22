"""Actual tuned pair and hybrid input stage, reservoir-loaded AC response."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for variant,root in [('hybrid',Path('/candidate'))]:
 prior=json.loads((root/'result.json').read_text());assert prior['sources_before']==prior['sources_after'];before=dict(prior['sources_before'])
 for n,h in before.items():assert sha(Path(n))==h
 parent=root/'VH.spice';pc=next(x for x in prior['cases'] if x['name']=='VH');assert sha(parent)==pc['artifacts_sha256']['.spice']
 body=parent.read_text().split('.control')[0]
 old='XOUT OUT X VDD VDD pfet_03v3 w=8u l=.5u m={8*S}'
 new=old.replace('m={8*S}','m={16*S}')
 assert body.count(old)==1
 body=body.replace(old,new)
 addition='''.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.include /screen/reference/reservoir_mim.spice
XCH OH 0 pt_ref_reservoir_2048
XCL OL 0 pt_ref_reservoir_2048
'''
 # Include dependency hashes for newly added reservoir/model files.
 def scan(text,parentdir):
  for line in text.splitlines():
   m=re.match(r'\s*\.(?:include|lib)\s+(\S+)',line,re.I)
   if not m:continue
   p=Path(m[1].strip(chr(34)+chr(39)));p=p if p.is_absolute() else parentdir/p
   if not p.is_file():assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
   p=p.resolve()
   if str(p) not in before:before[str(p)]=sha(p);scan(p.read_text(),p.parent)
 scan(addition,O);before[str(Path(__file__))]=sha(Path(__file__))
 for rail in ('h','l'):
  name=variant+'_'+rail;node='OH' if rail=='h' else 'OL'
  d=body+addition+f'ILOAD {node} 0 DC 0 AC 1\n'+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac dec 80 1k 1G
let zr=-real(v({node}))
let zi=-imag(v({node}))
wrdata /work/{name}.dat zr zi
.endc
.end
'''
  p=O/(name+'.spice');p.write_text(d);h=sha(p)
  with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
  assert sha(p)==h and before=={n:sha(Path(n)) for n in before}
  rows.append(dict(name=name,rail=rail,variant=variant,returncode=q.returncode,parent_sha256=sha(parent),sources_before=before.copy(),sources_after=before.copy(),artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}))
(O/'result.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
