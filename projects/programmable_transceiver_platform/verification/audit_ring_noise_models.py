"""Read the pinned running simulator's model files; preserve scoped excerpts."""
import hashlib,json,re,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
cid=(R/'scratch/transceiver-latest-rf-loop-selective/container.id').read_text().strip()
image=subprocess.check_output(['docker','inspect','--format','{{.Image}}',cid],text=True).strip()
assert image=='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
remote="""import json
from pathlib import Path
paths=[Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')/n for n in ('design.ngspice','sm141064.ngspice')]
print(json.dumps({str(p.resolve()):p.read_text() for p in paths}))
"""
files=json.loads(subprocess.check_output(['docker','exec',cid,'python3','-c',remote],text=True))
manifest=json.loads((R/'scratch/transceiver-vco-channel-kick/manifest.json').read_text());hashes={}
for path,s in files.items():
 h=hashlib.sha256(s.encode()).hexdigest();assert manifest['source_sha256_before'][path]==h;hashes[path]=h
model=next(s for p,s in files.items() if p.endswith('/sm141064.ngspice'))
def block(name):
 lines=model.splitlines();start=next(i for i,l in enumerate(lines) if l.lower().startswith('.subckt '+name+' '));end=next(i for i in range(start+1,len(lines)) if lines[i].lower().startswith('.ends'))
 return dict(first_line=start+1,last_line=end+1,text='\n'.join(lines[start:end+1]))
n=block('nfet_03v3');r=block('ppolyf_u');assert 'm0 d g s b nfet_03v3' in n['text']
resistors=[l.split()[0] for l in r['text'].splitlines() if re.match(r'^r\w+ ',l,re.I)];assert resistors==['rt1','rb','rt2']
excerpts=[]
for path,s in files.items():
 active=None
 for i,l in enumerate(s.splitlines()):
  if l.lower().startswith('.model '):active=l
  elif l and not l.startswith(('+','*')):active=None
  if 'fnoicor' in l.lower() or re.search(r'\bnfet_03v3_noi[abc]\b',l,re.I) or (active and re.match(r'\.model nfet_03v3(?:\s|\.)',active,re.I) and re.search(r'\b(noimod|fnoimod|tnoimod|noia|noib|noic|ef|af|kf)\s*=',l,re.I)):
   excerpts.append(dict(path=path,line=i+1,text=l,model=active))
assert excerpts
out=dict(completed=True,image=image,model_sha256=hashes,nfet_wrapper=n,load_resistor_wrapper=r,noise_parameter_excerpts=excerpts,load_resistor_internal_elements=resistors,expanded_resistive_elements_for_eight_loads=24,limitations=['Source inspection only; simulator noise contributions and effective active-bin coefficients still need measurement.', 'Each external load contains three resistive elements and substrate capacitors; one external pulse does not automatically reproduce all internal-source transfer functions.', 'Model noise settings are not measured silicon guarantees or complete unknown bounds.', 'No oscillator phase-noise PSD or jitter result.'])
(P/'evidence/ring-noise-models.json').write_text(json.dumps(out,indent=2)+'\n');print('Verified model hashes; excerpts:',len(excerpts));print('Each load resistor expands to',resistors)
