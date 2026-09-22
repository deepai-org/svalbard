"""Free-running seeded ring drives TX through existing AC-coupled restoring buffers."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']]+[Path('/screen/pll/ring_vco_split.spice')]
before={str(p):sha(p) for p in sources};assert all(before[p]==v for p,v in base['source_sha256_before'].items())
add='''.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.include /screen/pll/ring_vco_split.spice
VPLL PLLVDD 0 3.3
VCTRL CTRL 0 1.08
VREGEN REGEN 0 1.08
XVCO CTRL REGEN PLLVDD 0 CP CN pt_split_ring LOAD_L=5.25u CAP_W=4u CAP_L=3u
CLOADP CP 0 25f
CLOADN CN 0 25f
CCP CP LOIN 200f
CCN CN LOBIN 200f
RFBP LOIN XLP.MID 100k
RFBN LOBIN XLN.MID 100k
.ic v(XVCO.N0P)=1.718 v(XVCO.N0N)=1.714
.ic v(XVCO.N1P)=1.714 v(XVCO.N1N)=1.718
.ic v(XVCO.N2P)=1.718 v(XVCO.N2N)=1.714
'''
remove=['VLO LOIN 0 PULSE(0 3.3 1n 20p 20p 180p 400p)\n','VLOB LOBIN 0 PULSE(3.3 0 1n 20p 20p 180p 400p)\n']
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,addition=add,removed_lines=remove,scope='Seeded open-loop fixed-bias oscillator; ideal biases/supplies/coupling passives; fullscale TX only,40ns UIC.'),indent=2)+'\n');rows=[]
for variant in ('nmos','tg'):
 name=variant+'_c255';src=B/(name+'.spice');bc=next(c for c in base['cases'] if c['name']==name);assert sha(src)==bc['artifacts_sha256']['.spice'];d=src.read_text()
 for line in remove:assert d.count(line)==1;d=d.replace(line,'')
 d=d.replace('.control',add+'.control').replace('i(VLO) i(VLOB)','v(CP) v(CN) i(VPLL)').replace('tran 2p 10n 0 2p','tran 2p 40n 0 2p uic')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 assert sha(p)==pre
 rows.append(dict(name=name,baseline_deck_sha256=sha(src),deck_sha256_before=pre,returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n')
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
