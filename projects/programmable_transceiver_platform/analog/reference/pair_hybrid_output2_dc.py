"""Signed high-reference static load range; same output stage in both variants."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
probes=[f'v(XDUT.XHIGH.{n})' for n in ('A','T')] + [f'@m.xdut.xhigh.{dev}.m0[{q}]' for dev in ('xip','xin','xt','xmp','xmn','xout','xload') for q in ('vds','vdsat','id','gm','gds')]
rows=[]
for variant,root in [('hybrid',Path('/candidate'))]:
 prior=json.loads((root/'result.json').read_text());assert prior['sources_before']==prior['sources_after'];before=dict(prior['sources_before'])
 for n,h in before.items():assert sha(Path(n))==h
 before[str(Path(__file__))]=sha(Path(__file__))
 parent=root/'VH.spice';pc=next(c for c in prior['cases'] if c['name']=='VH');assert sha(parent)==pc['artifacts_sha256']['.spice'];body=parent.read_text().split('.control')[0]
 old='XOUT OUT X VDD VDD pfet_03v3 w=8u l=.5u m={8*S}'
 new=old.replace('m={8*S}','m={16*S}')
 assert body.count(old)==1
 body=body.replace(old,new)
 for direction,start,stop,step in [('up',-.01,.01,.00025),('down',.01,-.01,-.00025)]:
  name=variant+'_'+direction
  d=body+'.options reltol=1e-5 vntol=1e-8 abstol=1e-14\nILOAD OH 0 DC 0\n'+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save all {' '.join(probes)}
dc ILOAD {start} {stop} {step}
wrdata /work/{name}.dat v(OH) v(OL) v(XDUT.XHIGH.X) i(VDD) {' '.join(probes)}
.endc
.end
'''
  p=O/(name+'.spice');p.write_text(d)
  with (O/(name+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
  after={n:sha(Path(n)) for n in before};assert before==after
  rows.append(dict(name=name,parent_sha256=sha(parent),sources_before=before,sources_after=after,returncode=q.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
(O/'result.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
