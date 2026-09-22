"""Controlled PDK capacitor substitution; both streams at three MIM corners."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work'); B=Path('/baseline'); P=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice'); rows=[]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
base_result=json.loads((B/'result.json').read_text())
for corner in ('typical','ss','ff'):
 for sign in (-1,1):
  name=f'{corner}_first{sign}'; src=B/f'first{sign}.spice'; d=src.read_text()
  assert d.count('pt_cdac8_scaled')==1
  d=d.replace('pt_cdac8_scaled','pt_cdac8_mim')
  d=d.replace('.control',f'.lib {P}/sm141064.ngspice mimcap_{corner}\n.include /screen/adc/cdac8_mim.spice\n.control')
  d=d.replace(f'/work/first{sign}.dat',f'/work/{name}.dat')
  d=d.replace('v(SD7)\n','v(SD7) v(B7) v(B7B) v(xd.xp7.bot) v(xd.xn7.bot) v(VH) v(VL)\n')
  (O/f'{name}.spice').write_text(d)
  with (O/f'{name}.log').open('w') as log:
   subprocess.run(['ngspice','-b',str(O/f'{name}.spice')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
  rows.append(dict(name=name,corner=corner,first_sign=sign,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log')}))
  print('Completed '+name,flush=True)
r=dict(status='PDK_MIM_frames_unverified',cases=rows,source_sha256=base_result['source_sha256'])
for path in (Path('/screen/adc/cdac8_mim.spice'),P/'sm141064_mim.spice',P/'sm141064.ngspice'):
 r['source_sha256'][str(path)]=sha(path)
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
