"""Stationary retained LNA noise/load diagnostic, not a switched receiver model."""
import hashlib,json,re,subprocess,sys
BYPASS="--bypass" in sys.argv
MIM=next((a.split("=",1)[1] for a in sys.argv if a.startswith("--mim=")),None)
assert MIM in (None,"clean","lossy","inductive")
assert not (BYPASS and MIM)
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=""".include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /wifi/rf_lna/lna_cs_core.spice
.temp 27
VLNA LNAVDD 0 3.3
VBIAS LBIAS 0 1.5
VRF RFS 0 DC 0 AC 1
RRF RFS LIN 50
CCRF LIN LG 20p
RB LG LBIAS 1meg
RD LNAVDD RF 300
RS LS 0 82
XLNA LG RF LS 0 wifi_lna_cs_core
"""
if BYPASS:base += "CSB LS 0 20p\n"
if MIM:
 base += ".lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\n.include /screen/reference/reservoir_mim.spice\n"
 series={"clean":(0,0),"lossy":(5,300e-12),"inductive":(5,1e-9)}[MIM]
 if MIM=="clean":capnode="LS"
 else:
  base+=f"RCSB LS BPR {series[0]}\nLCSB BPR BPC {series[1]}\n"
  capnode="BPC"
 for count in (256,128,64):base+=f"XCSB{count} {capnode} 0 pt_ref_reservoir_{count}\n"
paths=set()
def deps(text,parent):
 for line in text.splitlines():
  m=re.match(r'\s*\.(?:include|inc|lib)\s+(\S+)',line,re.I)
  if not m:continue
  p=Path(m[1].strip('"\''));p=p if p.is_absolute() else parent/p
  if not p.is_file():assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2;continue
  p=p.resolve()
  if p not in paths:paths.add(p);deps(p.read_text(),p.parent)
deps(base,O);before={str(p):sha(p) for p in sorted(paths)}
scenarios=[dict(name='unloaded',sink=0,resistance=None,capacitance=0),dict(name='snapshot',sink=.003583217,resistance=1/.0058117,capacitance=.0028352/(2*3.141592653589793*2.51542263e9)),dict(name='heavy',sink=.004,resistance=100,capacitance=250e-15)]
rows=[]
for scenario in scenarios:
 for corner in (0,1):
  name=scenario['name']+f'_f{corner}'
  extra=f".param fnoicor={corner}\nILOAD RF 0 {scenario['sink']}\n"
  if scenario['resistance'] is not None:extra+=f"CISO RF LOAD 1u\nRLOAD LOAD 0 {scenario['resistance']}\nCLOAD RF 0 {scenario['capacitance']}\n"
  control=f""".control
set wr_singlescale
set wr_vecnames
set numdgt=15
op
wrdata /work/{name}-op.dat v(LG) v(LS) v(RF) i(VLNA) @m.xlna.x1.m0[vds] @m.xlna.x1.m0[vdsat]
ac lin 101 2.4g 2.6g
let gr=real(v(RF))
let gi=imag(v(RF))
let igr=real(v(LG))
let igi=imag(v(LG))
wrdata /work/{name}-ac.dat gr gi igr igi
noise v(RF) VRF lin 101 2.4g 2.6g 1
setplot noise1
wrdata /work/{name}.dat onoise_spectrum inoise_spectrum
wrdata /work/{name}-contributors.dat all
.endc
.end
"""
  p=O/(name+'.spice');p.write_text('* LNA stationary loading/noise diagnostic\n'+base+extra+control);h=sha(p)
  with (O/(name+'.log')).open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
  assert sha(p)==h
  rows.append(dict(name=name,scenario=scenario,fnoicor=corner,returncode=r.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat','-op.dat','-ac.dat','-contributors.dat') if (O/(name+e)).exists()}))
after={str(p):sha(p) for p in sorted(paths)};assert after==before
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');print('completed',len(rows))
