"""Matched 1kohm/500ohm input resistor diagnostic using retained DC/AC/noise decks."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bases={k:Path('/'+k+'baseline') for k in ('noise','interface')}
results={k:json.loads((p/'result.json').read_text()) for k,p in bases.items()}
sources={}
for r in results.values():
 assert r['source_sha256_before']==r['source_sha256_after']
 sources.update(r['source_sha256_before'])
assert all(sha(Path(p))==h for p,h in sources.items())
cell=Path('/screen/bb_filter_section.spice').read_text()
assert cell.count('RIP IP GP 1k')==cell.count('RIN IN GN 1k')==1
half=cell.replace('RIP IP GP 1k','RIP IP GP 500').replace('RIN IN GN 1k','RIN IN GN 500')
rows=[]
for variant in ('baseline','half'):
 for kind,r in results.items():
  for c in r['cases']:
   if c['name']=='resistor':continue
   directory=O/variant/kind;directory.mkdir(parents=True,exist_ok=True)
   name=c['name'];original=bases[kind]/(name+'.spice')
   assert sha(original)==c['artifacts_sha256']['.spice']
   d=original.read_text().replace('/work/',str(directory)+'/')
   if variant=='half':d=d.replace('.include /screen/bb_filter_section.spice',half.rstrip())
   p=directory/(name+'.spice');p.write_text(d);before=sha(p)
   with (directory/(name+'.log')).open('w') as f:
    s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=60)
   assert before==sha(p)
   exts=('.spice','.log','.dat','-integrated.dat' if kind=='noise' else '-op.dat')
   rows.append(dict(variant=variant,kind=kind,name=name,returncode=s.returncode,baseline_deck_sha256=sha(original),artifacts_sha256={e:sha(directory/(name+e)) for e in exts if (directory/(name+e)).exists()}))
after={p:sha(Path(p)) for p in sources};assert after==sources
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=sources,source_sha256_after=after),indent=2)+'\n')
print('completed',len(rows),'cases')
