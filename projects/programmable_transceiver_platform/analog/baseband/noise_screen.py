"""Stationary filter noise diagnostic with resistor calibration; not mixer noise."""
import hashlib,json,re,subprocess,sys
CONTRIBUTORS="--contributors" in sys.argv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spice_sources import collect_sources, __file__ as source_scanner_file
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=""".include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_filter_section.spice
.temp 27
"""
paths=set()
paths.add(Path(source_scanner_file))
collect_sources(base, O, paths)
before={str(p):sha(p) for p in sorted(paths)}
# Save exact noise-related source lines, with locations and hashes; presence is not validation.
excerpts=[]
for p in sorted(paths):
 for number,line in enumerate(p.read_text().splitlines(),1):
  if re.search(r"fnoicor|(?:^|\s)(?:fnoimod|tnoimod|noia|noib|noic|ef)\s*=",line,re.I):
   excerpts.append(dict(path=str(p),line=number,text=line))
(O/'model-noise-lines.json').write_text(json.dumps(excerpts,indent=2)+'\n')
rows=[]
for name,corner in [('resistor',None),('filter_f0',0),('filter_f1',1)]:
 if corner is None:
  circuit='VS SIG 0 DC 0 AC 1\nRTEST SIG OP 1000\n'
  output='v(OP)'
 else:
  circuit=f""".param fnoicor={corner}
VDD VDD 0 3.3
VB BIAS 0 2.25
VCM CM 0 .9
VS SIG 0 DC 0 AC 1
EP SP CM SIG 0 .5
EN SN CM SIG 0 -.5
RP SP IP 1000
RN SN IN 1000
XDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB=20k C=20p
"""
  output='v(OP,ON)'
 control=f""".control
set wr_singlescale
set wr_vecnames
set numdgt=15
noise {output} VS dec 40 1k 100meg
setplot noise1
wrdata /work/{name}.dat onoise_spectrum inoise_spectrum
setplot noise2
wrdata /work/{name}-integrated.dat onoise_total inoise_total
.endc
.end
"""
 if CONTRIBUTORS:
  control=control.replace('dec 40 1k 100meg\n','dec 40 1k 100meg 1\n').replace(f'wrdata /work/{name}.dat onoise_spectrum inoise_spectrum',f'wrdata /work/{name}.dat onoise_spectrum inoise_spectrum\nwrdata /work/{name}-contributors.dat all')
 d='* Stationary noise diagnostic\n'+base+circuit+control
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as f:
  s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
 assert sha(p)==h
 rows.append(dict(name=name,fnoicor=corner,returncode=s.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in (('.spice','.log','.dat','-integrated.dat','-contributors.dat') if CONTRIBUTORS else ('.spice','.log','.dat','-integrated.dat')) if (O/(name+e)).exists()}))
after={str(p):sha(p) for p in sorted(paths)};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after,model_excerpts_sha256=sha(O/'model-noise-lines.json')),indent=2)+'\n')
print([(c['name'],c['returncode']) for c in rows])
