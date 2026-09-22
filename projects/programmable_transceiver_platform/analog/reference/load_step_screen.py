"""Signed finite reference load pulses; diagnostic demand, not a load bound."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path(p) for p in base['source_sha256']];before={str(p):sha(p) for p in sources};rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,rails=['high','low'],loads_ma=[-2,2],scope='10ns signed2mA pulse after unloaded OP; tuned reference and same2048-unit reservoir; not startup or ADC load bound'),indent=2)+'\n')
for rail in ('high','low'):
 for load in (-2,2):
  name=f'{rail}_{load:g}ma';src=B/f'{rail}_mim2048_i0_cc2_rz2000.spice';old=next(c for c in base['cases'] if c['name']==src.stem);assert sha(src)==old['artifacts_sha256']['.spice']
  d=src.read_text().split('.control')[0];assert d.count('ILOAD OUT 0 DC 0 AC 1')==1
  d=d.replace('ILOAD OUT 0 DC 0 AC 1',f'ILOAD OUT 0 PWL(0 0 20n 0 20.1n {load}m 30n {load}m 30.1n 0)')
  d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ntran 20p 200n 0 20p\n'+f'wrdata /work/{name}.dat v(OUT) v(XBUF.X) v(XBUF.T) i(VDD) v(TARGET)\n.endc\n.end\n'
  p=O/(name+'.spice');p.write_text(d);pre=sha(p)
  with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
  rows.append(dict(name=name,rail=rail,load_ma=load,returncode=r.returncode,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
