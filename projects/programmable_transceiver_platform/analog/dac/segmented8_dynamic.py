"""Actual segmented DAC major-carry load/skew matrix, unchanged DC core."""
import hashlib,json,re,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'segmented.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());assert sha(src)==base['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_after']]+[Path('/screen/reference/reservoir_mim.spice')];before={str(p):sha(p) for p in sources}
vectors=['v(OP)','v(ON)','v(BN)','i(VDRV)']+[f'v(D{i})' for i in range(8)]+[f'v(XD.T{k})' for k in range(1,16)]
vectors += [f'v(XD.{s})' for i in range(4) for s in (f'L{i}',f'L{i}B')]+[f'v(XD.{s})' for k in range(1,16) for s in (f'H{k}',f'H{k}B')]
vectors += [f'v(XD.XCL{i}.T)' for i in range(4)]+[f'v(XD.XCH{k}.T)' for k in range(1,16)]
manifest=dict(source_sha256_before=before,baseline_deck_sha256=sha(src),vectors=vectors,planned_cases=[f'c{u}_skew{s:g}' for u in (32,128) for s in (-.2,0,.2)])
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');rows=[]
for units in (32,128):
 for skew in (-.2,0,.2):
  name=f'c{units}_skew{skew:g}'
  original=src.read_text().split('.control')[0]
  d=re.sub(r'^BD\d+ .+\n','',original,flags=re.M).replace('VCODE CODE 0 0\n','')
  d+='.include /screen/reference/reservoir_mim.spice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\n'
  for i in range(8):
   first=3.3 if i<7 else 0;other=3.3-first;shift=skew if i==7 else 0;t1=30+shift;t2=55+shift
   d+=f'VD{i} D{i} 0 PWL(0 {first:g} {t1:g}n {first:g} {t1+.1:g}n {other:g} {t2:g}n {other:g} {t2+.1:g}n {first:g})\n'
  d+=f'XCP OP 0 pt_ref_reservoir_{units}\nXCN ON 0 pt_ref_reservoir_{units}\n'
  d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ntran 5p 79.9n 0 5p\n'+f'wrdata /work/{name}.dat '+' '.join(vectors)+'\n.endc\n.end\n'
  path=O/(name+'.spice');path.write_text(d);deckhash=sha(path)
  with (O/(name+'.log')).open('w') as log:
   try:
    r=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=r.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
  assert sha(path)==deckhash
  rows.append(dict(name=name,load_units=units,msb_skew_ns=skew,returncode=code,timed_out=timeout,deck_sha256_before=deckhash,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');assert before==after
