"""Dual ADC reference topology and sizing experiments."""
import hashlib,json,subprocess,time
from pathlib import Path
B=Path('/candidate_base');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(variant='hybrid', *, entrypoint=None):
 scope={
  'hybrid':'Five high-reference input/tail/mirror devices use NMOS-input topology; PMOS output and all ADC circuitry/history retained.',
  'output2':'Five high-reference input/tail/mirror devices use NMOS-input topology; PMOS output multiplicity doubled; all ADC circuitry/history retained.',
  'long-mirror':'Four reference mirror devices W8u/L.5u toW16u/L1u only; all ADC circuitry and history retained.',
 }[variant]
 r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 before={}
 for name,h in r['source_sha256_before'].items():
  p=Path(name);assert sha(p)==h,name;before[name]=h
 before[str(Path(__file__))]=sha(Path(__file__))
 before[str(Path(entrypoint or __file__))]=sha(Path(entrypoint or __file__))
 assert sha(B/'frames.spice')==r['artifacts_sha256']['.spice']
 base=(B/'frames.spice').read_text()
 anchor='.include /screen/reference/adc_reference_pair_tuned.spice';assert base.count(anchor)==1
 pair=Path('/screen/reference/adc_reference_pair_tuned.spice').read_text();expanded=pair;changes=[]
 for filename in ('buffer_scaled_tune.spice','buffer_complement_tune.spice'):
  cell=Path('/screen/reference',filename).read_text();changed=cell
  if variant=='long-mirror':
   for line in cell.splitlines():
    if line.startswith(('XMP ','XMN ')):
     assert 'w=8u l=.5u' in line
     new=line.replace('w=8u l=.5u','w=16u l=1u');changed=changed.replace(line,new);changes.append((line,new))
  elif filename=='buffer_complement_tune.spice':
   ncell=Path('/screen/reference/buffer_scaled_tune.spice').read_text()
   for instance in ('XIP','XIN','XT','XMP','XMN'):
    old=next(l for l in cell.splitlines() if l.startswith(instance+' '))
    new=next(l for l in ncell.splitlines() if l.startswith(instance+' '))
    changed=changed.replace(old,new);changes.append((old,new))
   if variant=='output2':
    old='XOUT OUT X VDD VDD pfet_03v3 w=8u l=.5u m={8*S}'
    new=old.replace('m={8*S}','m={16*S}')
    assert changed.count(old)==1
    changed=changed.replace(old,new);changes.append((old,new))
  expanded=expanded.replace('.include /screen/reference/'+filename,changed)
 assert len(changes)=={'hybrid':5,'output2':6,'long-mirror':4}[variant]
 deck=base.replace(anchor,expanded);assert deck.replace(expanded,anchor)==base
 cell=expanded
 oldout='/work/probed/frames.dat';assert deck.count(oldout)==1;deck=deck.replace(oldout,'/work/frames.dat')
 p=O/'frames.spice';p.write_text(deck)
 m=dict(parent_deck_sha256=sha(B/'frames.spice'),deck_sha256_before=sha(p),source_sha256_before=before,changes=changes,added_subcircuit=cell,scope=scope,evaluation='Compare both gate transition directions, charge/peaks, all reference decision errors, held voltages, codes and driver supply energy. No automatic promotion from a reduced peak.')
 (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');start=time.monotonic()
 with (O/'frames.log').open('w') as log:
  try:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=1800);code=q.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==m['deck_sha256_before']
 (O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)

if __name__ == '__main__':
 main()
