"""Filter common-mode and finite-source loading screen; no stability claim."""
import hashlib,json,re,subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spice_sources import collect_sources, __file__ as source_scanner_file
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_filter_section.spice
.temp 27
VDD VDD 0 3.3
VB BIAS 0 2.25
XDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB=20k C=20p
'''
paths=set()
paths.add(Path(source_scanner_file))
collect_sources(base, O, paths);before={str(p):sha(p) for p in sorted(paths)}
probes=[f'v({n})' for n in ('IP','IN','XDUT.GP','XDUT.GN','XDUT.MP','XDUT.MN','OP','ON','XDUT.T1','XDUT.T2')]+['i(VIP)','i(VIN)','i(VDD)']+[f'@m.xdut.{stage}.{dev}.m0[{p}]' for stage in ('xa','xb') for dev in ('xip','xin','xtail') for p in ('vds','vdsat')]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,common_mode_v=[.6,.9,1.177],source_ohm_per_leg=[0,1000],op_probes=probes,scope='TT27C3.3V external bias2.25V; original RFB20k/C20p; source/load scenarios not fab bounds'),indent=2)+'\n')
rows=[]
for cm in (.6,.9,1.177):
 for rs in (0,1000):
  name=f'cm{cm:g}_r{rs}'
  stim=f'VIP {"SP" if rs else "IP"} 0 DC {cm} AC .5\nVIN {"SN" if rs else "IN"} 0 DC {cm} AC .5 180\n'
  if rs:stim+=f'RP SP IP {rs}\nRN SN IN {rs}\n'
  d='* Actual filter interface screen\n'+base+stim+'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\n'+f'wrdata /work/{name}-op.dat '+' '.join(probes)+'\nac lin 100 1meg 100meg\nlet gr=real(v(OP)-v(ON))\nlet gi=imag(v(OP)-v(ON))\nlet ir=real(v(IP)-v(IN))\nlet ii=imag(v(IP)-v(IN))\n'+f'wrdata /work/{name}.dat gr gi ir ii\n.endc\n.end\n'
  p=O/(name+'.spice');p.write_text(d);h=sha(p)
  with (O/(name+'.log')).open('w') as f:s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
  assert sha(p)==h
  rows.append(dict(name=name,common_mode_v=cm,source_ohm_per_leg=rs,returncode=s.returncode,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat','-op.dat') if (O/(name+e)).exists()}))
assert before=={str(p):sha(p) for p in sorted(paths)}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=before),indent=2)+'\n');print([(c['name'],c['returncode']) for c in rows])
