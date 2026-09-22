"""Actual code-driver/DAC major-carry transitions with PDK capacitive loads."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'v2.15_r100.spice';base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==next(c for c in base['cases'] if c['name']=='v2.15_r100')['artifacts_sha256']['.spice']
sources=list(map(Path,base['source_sha256_after']))+[Path('/screen/adc/code_driver_small.spice'),Path('/screen/reference/reservoir_mim.spice')]
before={str(p):sha(p) for p in sources}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),planned_load_units=[32,128],planned_msb_skew_ns=[-.2,0,.2],scope='127->128->127 at30/55ns, actual asymmetric code drivers, ideal commands and bias/termination'),indent=2)+'\n')
for units in (32,128):
 for skew in (-.2,0,.2):
  name=f'c{units}_skew{skew:g}';d=src.read_text().split('.control')[0]
  d=re.sub(r'^(?:B\d+|BB\d+) .+\n','',d,flags=re.M);d=d.replace('VCODE CODE 0 0\n','')
  d+='.include /screen/adc/code_driver_small.spice\n.include /screen/reference/reservoir_mim.spice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\nVDRV VDRV 0 3.3\n'
  for bit in range(8):
   first=3.3 if bit<7 else 0;other=3.3-first;shift=skew if bit==7 else 0;t1=30+shift;t2=55+shift
   d+=f'VD{bit} D{bit} 0 PWL(0 {first:g} {t1:g}n {first:g} {t1+.1:g}n {other:g} {t2:g}n {other:g} {t2+.1:g}n {first:g})\n'
   d+=f'XDRV{bit} D{bit} B{bit} B{bit}B VDRV 0 pt_adc_code_small_driver WEIGHT={2**bit}\n'
  d+=f'XCP OP 0 pt_ref_reservoir_{units}\nXCN ON 0 pt_ref_reservoir_{units}\n'
  vectors='v(OP) v(ON) v(BN) i(VDRV) '+ ' '.join(f'v(B{i}) v(B{i}B)' for i in range(8))+' '+' '.join(f'v(D{i})' for i in range(8))
  d+=f'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ntran 5p 79.9n 0 5p\nwrdata /work/{name}.dat {vectors}\n.endc\n.end\n'
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=300)
  rows.append(dict(name=name,load_units=units,msb_skew_ns=skew,returncode=r.returncode,artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}));print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(status='major_carry_DAC_dynamic_unverified',cases=rows,source_sha256_before=before,source_sha256_after=after,baseline_deck_sha256=sha(src),limitations=['Only127/128 switching, ideal command generator, bias and termination supply/resistors.', 'PDK load capacitors are declared scenarios, not extracted loading bounds.', 'Nominal matched FET/MIM only; no mismatch/noise/SFDR or complete TX path.', '5ps maximum step; glitch metrics need numerical sensitivity checks before precision claims.']),indent=2)+'\n')
