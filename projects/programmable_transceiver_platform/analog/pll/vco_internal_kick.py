"""Loaded open-loop ring supply sensitivity; deterministic diagnostic only."""
import hashlib,json,re,subprocess,sys
RIPPLE="--ripple" in sys.argv
FINE="--fine" in sys.argv

from pathlib import Path
O=Path('/work');B=Path('/baseline/v1.08.spice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B.parent/'result.json').read_text());c=next(c for c in r['cases'] if c['control_v']==1.08)
assert sha(B)==c['artifacts_sha256']['.spice']
original=B.read_text();assert '.ic v(XRX.XVCO.N0P)=' in original and 'v(XRX.XVCO.N0N)=' in original
assert original.count('VPLL PLLVDD 0 3.3')==1
paths={B,Path(__file__)}
def dependencies(text,parent):
 for line in text.splitlines():
  match=re.match(r'\s*\.(?:include|inc|lib)\s+(\S+)',line,re.I)
  if not match:continue
  name=match.group(1).strip('"\'')
  candidate=Path(name)
  if not candidate.is_absolute():candidate=parent/candidate
  if not candidate.is_file():
   # .lib section declarations have a bare section name, not a file.
   assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2, line
   continue
  candidate=candidate.resolve()
  if candidate in paths:continue
  paths.add(candidate);dependencies(candidate.read_text(),candidate.parent)

dependencies(original,B.parent)
before={str(p):sha(p) for p in sorted(paths)}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,max_step_ps=.5 if FINE else 2,baseline_deck_sha256=sha(B),pulse_nodes=['XRX.XVCO.N0P','XRX.XVCO.N0N'],pulse_times_ns=[20,20.001,20.011,20.012],amplitudes_a=[0,1e-4,-1e-4],scope='Deterministic differential internal-stage charge perturbation; no intrinsic noise or autonomous PLL claim'),indent=2)+'\n')
rows=[]
for name,amplitude in [('quiet',0),('positive',1e-4),('negative',-1e-4)]:
 pulse=f'IKICK XRX.XVCO.N0P XRX.XVCO.N0N PWL(0n 0 20n 0 20.001n {amplitude} 20.011n {amplitude} 20.012n 0)\n'
 d=original.replace('.control',pulse+'.control').replace('/work/v1.08.dat',f'/work/{name}.dat')
 assert d.replace(pulse,'').replace(f'/work/{name}.dat','/work/v1.08.dat')==original
 if FINE:d=d.replace('tran 2p 41n 0 2p uic','tran .5p 41n 0 .5p uic')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:
   result=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600 if FINE else 300);code=result.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,pulse_a=amplitude,returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sorted(paths)};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
