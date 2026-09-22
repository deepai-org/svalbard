"""Finite-load static transfer: expose swing/compliance hidden by ideal clamps."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());src=B/'cm1.65.spice';rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==next(c for c in base['cases'] if c['name']=='cm1.65')['artifacts_sha256']['.spice']
before={path:sha(Path(path)) for path in base['source_sha256_after']};assert before==base['source_sha256_after']
for term in (2.15,3.3):
 for resistance in (50,100,200,400):
  name=f'v{term:g}_r{resistance}';d=src.read_text();old='VOP OP 0 1.65\nVON ON 0 1.65\n';assert d.count(old)==1
  d=d.replace(old,f'VTERM TERM 0 {term}\nRP TERM OP {resistance}\nRN TERM ON {resistance}\n').replace('/work/cm1.65.dat',f'/work/{name}.dat').replace('i(VOP) i(VON)','v(OP) v(ON)')
  (O/(name+'.spice')).write_text(d)
  (O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),planned_matrix=dict(termination_v=[2.15,3.3],resistance_ohm=[50,100,200,400]),scope='Matched TT static sweep, ideal termination supply and resistors'),indent=2)+'\n')
  with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=120)
  rows.append(dict(name=name,termination_v=term,resistance_ohm=resistance,returncode=r.returncode,artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}))
after={path:sha(Path(path)) for path in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(status='finite_load_DAC_DC_unverified',cases=rows,baseline_deck_sha256=sha(src),source_sha256_before=before,source_sha256_after=after,limitations=['Ideal resistive terminations and termination supply, ideal code control and20uA bias.', 'Matched static FET typical only; no physical resistor variation, current mismatch or output capacitance.', 'No dynamic glitch/settling, reconstruction/mixer or RF modulation qualification.']),indent=2)+'\n');print('Completed eight finite-load transfer cases.')
