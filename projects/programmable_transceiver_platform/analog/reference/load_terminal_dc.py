"""Separate steady terminal current from reported channel ID at load biases."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=list(PDK.glob('*.spice'))+list(PDK.glob('*.ngspice'))+[Path(__file__)]
before={str(p):sha(p) for p in sources}
deck='''* DC load terminal accounting, no displacement current.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.temp 27
'''
cases=[];probes=[]
for kind,center,gate,supply,model in [('n',2.15,.796,0,'nfet_03v3'),('p',1.15,2.273,3.3,'pfet_03v3')]:
 for index,offset in enumerate((-.1,0,.1)):
  name=kind+str(index);drain=center+offset
  for port,node,value in [('D','DRAIN',drain),('G','GATE',gate),('B','BODY',supply),('S','SOURCE',supply)]:
   deck+=f'V{port}{name} {node}{name} 0 {value}\n'
  deck+=f'X{name} DRAIN{name} GATE{name} SOURCE{name} BODY{name} {model} w=8u l=.5u m=256\n'
  probes.extend([f'i(V{port}{name})' for port in ('D','G','B','S')]+[f'@m.x{name}.m0[id]'])
  cases.append(dict(type=kind,drain_v=drain,gate_v=gate,source_body_v=supply))
deck+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\nwrdata /work/probe.dat '+' '.join(probes)+'\n.endc\n.end\n'
p=O/'probe.spice';p.write_text(deck)
with (O/'probe.log').open('w') as log:
 r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert r.returncode==0
a=np.loadtxt(O/'probe.dat',skiprows=1);assert a.shape==(31,) and np.isfinite(a).all()
for j,case in enumerate(cases):
 d,g,b,s=-a[1+j*5:5+j*5];channel=a[5+j*5]*(1 if case['type']=='n' else -1)
 case.update(drain_current_a=float(d),gate_current_a=float(g),body_current_a=float(b),source_current_a=float(s),
  signed_reported_channel_a=float(channel),drain_minus_channel_a=float(d-channel),terminal_kcl_error_a=float(d+g+b+s))
 assert abs(d+g+b+s)<1e-10
 print(case)
after={str(p):sha(p) for p in sources};assert before==after
report=dict(cases=cases,source_hashes_before=before,source_hashes_after=after,
 artifacts_sha256={ext:sha(O/('probe'+ext)) for ext in ('.spice','.log','.dat')},
 limitations=['Selected typical DC points only; fixed gate biases do not cover shared-bias motion.',
 'DC terminal-minus-channel current is not displacement; mechanism identification needs model/branch evidence.',
 'PDK simulation is not measured silicon or corner/yield qualification.'])
(O/'result.json').write_text(json.dumps(report,indent=2)+'\n')
