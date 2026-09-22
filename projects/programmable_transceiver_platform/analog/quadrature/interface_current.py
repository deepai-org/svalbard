"""Observation-only zero-volt sensor: positive current flows into both mixers."""
import hashlib,json,subprocess,sys
HALF="--half" in sys.argv
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());sources=[Path(p) for p in r['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==r['source_sha256_after']
manifest=dict(source_sha256_before=before,baseline_deck_sha256={},half_width=HALF,scope='Zero-volt source from LNA drain RF to combined mixer port MIXRF; positive current into mixers; original circuit otherwise unchanged')
if HALF:manifest['scope']='Half-width mixer fingers with zero-volt input-current sensor; all other circuit parameters unchanged'
rows=[]
for old in r['cases']:
 name=old['name'];src=B/(name+'.spice');assert sha(src)==old['artifacts_sha256']['.spice'];manifest['baseline_deck_sha256'][name]=sha(src)
 d=src.read_text().replace('XMI RF OIP','XMI MIXRF OIP').replace('XMQ RF OQP','XMQ MIXRF OQP').replace('.control','VSENSE RF MIXRF 0\n.control')
 d='\n'.join(line+' v(MIXRF) i(VSENSE)' if line.startswith('wrdata ') else line for line in d.splitlines())+'\n'
 if HALF:
  cell=Path('/wifi/rf_switch_mixer/mixer.spice').read_text();assert cell.count('w=4u l=0.28u')==16
  d=d.replace('.include /wifi/rf_switch_mixer/mixer.spice\n',cell.replace('w=4u l=0.28u','w=2u l=0.28u'))
 p=O/(name+'.spice');p.write_text(d);h=sha(p);(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 with (O/(name+'.log')).open('w') as f:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=600);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,amplitude_v=old["amplitude_v"],returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
