"""Independently excite load MOS drain/gate; small-signal terminal admittance."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=list(PDK.glob('*.spice'))+list(PDK.glob('*.ngspice'))+[Path(__file__)]
before={str(p):sha(p) for p in sources}
deck='''* Independent AC columns, nominal load device size. Not an autonomous reference.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.temp 27
VS S 0 3.3
'''
cases=[]
for kind,drain,gate,source,model in [('n',2.15,.796,'0','nfet_03v3'),('p',1.15,2.273,'S','pfet_03v3')]:
 for excite in ('d','g'):
  name=kind+excite
  deck+=f'VD{name} DRAIN{name} 0 DC {drain} AC {int(excite=="d")}\nVG{name} GATE{name} 0 DC {gate} AC {int(excite=="g")}\n'
  deck+=f'X{name} DRAIN{name} GATE{name} {source} {source} {model} w=8u l=.5u m=256\n'
  cases.append(dict(name=name,type=kind,excitation=excite,drain_v=drain,gate_v=gate))
deck+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nac dec 3 1meg 1g\n'
probes=[]
for case in cases:
 name=case['name']
 # Source current is inward to the ideal voltage source, opposite device current.
 deck+=f'let re_{name} = -real(i(VD{name}))\nlet im_{name} = -imag(i(VD{name}))\n'
 probes.extend(['re_'+name,'im_'+name])
deck+='wrdata /work/probe.dat '+' '.join(probes)+'\n.endc\n.end\n'
p=O/'probe.spice';p.write_text(deck)
with (O/'probe.log').open('w') as log:
 result=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert result.returncode==0
a=np.loadtxt(O/'probe.dat',skiprows=1)
assert a.ndim==2 and a.shape[1]==9 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
for index,case in enumerate(cases):
 case['samples']=[dict(frequency_hz=float(row[0]),drain_conductance_s=float(row[1+2*index]),
  drain_susceptance_s=float(row[2+2*index]),effective_charge_derivative_f=float(row[2+2*index]/(2*np.pi*row[0]))) for row in a]
after={str(p):sha(p) for p in sources};assert before==after
out=dict(cases=cases,source_hashes_before=before,source_hashes_after=after,
 artifacts_sha256={ext:sha(O/('probe'+ext)) for ext in ('.spice','.log','.dat')},
 limitations=['Linearized selected nominal DC points with independently stiff terminals; shared bias dynamics are absent.',
 'Imaginary admittance divided by angular frequency is an effective terminal charge derivative, not automatically a lumped passive capacitance.',
 'No noise, mismatch, transient large-signal or independent SAR validation claim.'])
(O/'result.json').write_text(json.dumps(out,indent=2)+'\n')
for case in cases:print(case['name'],case['samples'][0],case['samples'][-1])
