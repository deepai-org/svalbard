"""Finite-source differential DC transfer, retaining each completed AC circuit."""
import hashlib,json,subprocess
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
before=dict(r['source_sha256_before'])
for name,h in before.items():assert sha(Path(name))==h
before[str(Path(__file__))]=sha(Path(__file__))
rows=[]
for c in r['cases']:
 n=c['name'];parent=B/(n+'.spice');assert sha(parent)==c['artifacts_sha256']['.spice'] and c['returncode']==0
 body=parent.read_text().split('.control')[0];cm=c['common_mode_v'];old=f'VIP SP 0 DC {cm} AC .5\nVIN SN 0 DC {cm} AC .5 180'
 new=f'VCM CM 0 {cm}\nVD D 0 0\nEP SP CM D 0 .5\nEN SN CM D 0 -.5';assert body.count(old)==1;body=body.replace(old,new)
 assert body.replace(new,old)==parent.read_text().split('.control')[0]
 probes=['v(SP)','v(SN)','v(IP)','v(IN)','v(OP)','v(ON)','v(XDUT.T1)','v(XDUT.T2)','i(VDD)']
 probes += [f'@m.xdut.{stage}.{dev}.m0[{q}]' for stage in ('xa','xb') for dev in ('xip','xin','xtail') for q in ('vds','vdsat')]
 d=body+'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nsave all '+' '.join(probes)+'\ndc VD -.4 .4 .005\n'+f'wrdata /work/{n}.dat '+' '.join(probes)+'\n.endc\n.end\n'
 p=O/(n+'.spice');p.write_text(d);h=sha(p)
 with (O/(n+'.log')).open('w') as log:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 assert sha(p)==h
 rows.append(dict(name=n,common_mode_v=cm,feedback_ohm=c['feedback_ohm'],returncode=q.returncode,parent_sha256=sha(parent),probes=probes,artifacts_sha256={ext:sha(O/(n+ext)) for ext in ('.spice','.log','.dat') if (O/(n+ext)).exists()}))
after={n:sha(Path(n)) for n in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=before,sources_after=after),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
