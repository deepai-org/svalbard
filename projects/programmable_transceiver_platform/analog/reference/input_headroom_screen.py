"""High-reference input width DC diagnostic; no candidate adoption."""
import hashlib,json,subprocess,sys
TAIL="--tail" in sys.argv
from pathlib import Path
import numpy as np
O=Path('/work'); B=Path('/baseline')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((B/'result.json').read_text())
sources=[Path(p) for p in old['source_sha256']]
before={str(p):sha(p) for p in sources}
src=B/'high_mim2048_i0_cc2_rz2000.spice'
case=next(c for c in old['cases'] if c['name']==src.stem)
assert sha(src)==case['artifacts_sha256']['.spice']
cell=Path('/screen/reference/buffer_complement_tune.spice').read_text()
probes=['v(OUT)','v(XBUF.T)','i(VDD)']+[f'@m.xbuf.{dev}.m0[{p}]' for dev in ('xin','xip','xt','xout','xload') for p in ('vds','vdsat','id')]
manifest=dict(source_sha256_before=before,baseline_deck_sha256=sha(src),width_factors=[1,2,4],targets_v=[2,2.15,2.3],loads_a=[-.002,0,.002],probes=probes,tail_mode=TAIL,scope='TT27C3.3V DC diagnostic; signed loads and target offsets are scenarios, not bounds')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
rows=[]
for factor in manifest['width_factors']:
 lines=cell.splitlines()
 for i,line in enumerate(lines):
  if line.startswith(('XIP ','XIN ')):
   assert 'w=8u' in line;lines[i]=line.replace('w=8u',f'w={32 if TAIL else 8*factor}u')
 candidate='\n'.join(lines)+'\n'
 if not TAIL and factor==1: assert candidate==cell
 if TAIL and factor!=1:
  candidate=candidate.replace('XT T BP VDD VDD pfet_03v3 w=8u l=.5u m={16*S}',f'XT T BPT VDD VDD pfet_03v3 w=8u l=.5u m={{{16*factor}*S}}')
  candidate=candidate.replace('RC X Z',f'IBPT BPT VSS 20u\nXBPT BPT BPT VDD VDD pfet_03v3 w=8u l=.5u m={factor}\nRC X Z')
 for target in manifest['targets_v']:
  for load in manifest['loads_a']:
   name=f'w{factor}_v{target:g}_i{load:g}'
   d=src.read_text().split('.control')[0].replace('.include /screen/reference/buffer_complement_tune.spice',candidate).replace('VT TARGET 0 2.15',f'VT TARGET 0 {target}').replace('ILOAD OUT 0 DC 0 AC 1',f'ILOAD OUT 0 DC {load}')
   d+=' .control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\nwrdata /work/'+name+'.dat '+' '.join(probes)+'\n.endc\n.end\n'
   p=O/(name+'.spice');p.write_text(d);h=sha(p)
   with (O/(name+'.log')).open('w') as f:
    r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=120)
   assert r.returncode==0 and 'aborted' not in (O/(name+'.log')).read_text().lower()
   dat=O/(name+'.dat')
   assert dat.read_text().splitlines()[0].lower().split()[1:]==[v.lower() for v in probes]
   a=np.loadtxt(dat,skiprows=1);assert a.shape==(len(probes)+1,) and np.isfinite(a).all()
   assert sha(p)==h
   rows.append(dict(name=name,width_factor=factor,target_v=target,load_a=load,returncode=r.returncode,deck_sha256_before=h,values=dict(zip(probes,map(float,a[1:]))),artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log')}))
assert before=={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=before),indent=2)+'\n')
print('Completed',len(rows),'DC cases')
