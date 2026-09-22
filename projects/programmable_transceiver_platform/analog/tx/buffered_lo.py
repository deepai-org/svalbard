"""Actual two-stage CMOS LO buffers connected to both TX bridge candidates."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']]+[Path('/screen/lo_buffer.spice')]
before={str(p):sha(p) for p in sources};assert all(before[p]==v for p,v in base['source_sha256_before'].items())
extra='v(LOIN) v(LOBIN) i(VLOBUF)'
add='.include /screen/lo_buffer.spice\nVLOBUF VLOBUF 0 3.3\nXLP LOIN LO VLOBUF 0 pt_lo_buffer S=1\nXLN LOBIN LOB VLOBUF 0 pt_lo_buffer S=1\n'
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,extra_vectors=extra,scope='Only insert two S1 PDK CMOS buffers; source clocks, DAC, loads and10ns horizon unchanged. Ideal separate3.3V driver supply.'),indent=2)+'\n');rows=[]
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice']
 d=src.read_text().replace('VLO LO 0 PULSE','VLO LOIN 0 PULSE').replace('VLOB LOB 0 PULSE','VLOB LOBIN 0 PULSE').replace('.control',add+'.control')
 lines=d.splitlines();lines=[l+' '+extra if l.startswith(('save ','wrdata ')) else l for l in lines];d='\n'.join(lines)+'\n'
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=240);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 assert sha(p)==pre
 rows.append(dict(name=name,returncode=rc,timed_out=timeout,baseline_deck_sha256=sha(src),deck_sha256_before=pre,elapsed_seconds=time.monotonic()-start,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
