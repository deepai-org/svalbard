"""Finite-swing source into PDK RC splitter and actual self-biased buffers."""
import hashlib,json,subprocess,sys
RING="--ring" in sys.argv
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());c=r['cases'][0];assert sha(B/'load25.spice')==c['artifacts_sha256']['.spice']
sources=[Path(p) for p in r['source_sha256_before']];assert {str(p):sha(p) for p in sources}==r['source_sha256_after']
if RING:sources.append(Path('/screen/pll/ring_vco_split.spice'))
before={str(p):sha(p) for p in sources}
base=(B/'load25.spice').read_text().split('.control')[0]
probes=[f'v({n})' for n in ('IP','IN','QP','QN','BIP','BIN','BQP','BQN','OIP','OIN','OQP','OQN')]+['i(VBUF)']
if RING:probes+=['v(P)','v(N)','i(VPLL)']
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(B/'load25.spice'),ring_mode=RING,single_leg_peak_v=[.2,.4] if not RING else [None],frequency_hz=2.5e9,horizon_ns=81,probes=probes,scope='Seeded actual ring with UIC; fixed ideal control/regeneration,CM,supplies; no PLL or cold startup' if RING else 'Ideal differential sinusoid,OP initialization; not actual oscillator or cold startup'),indent=2)+'\n')
rows=[]
for amp in ((.2,.4) if not RING else (.4,)):
 name=f'a{amp:g}';d=base.replace('VP SP 0 DC 1.5 AC .5',f'VP SP 0 SIN(1.5 {amp} 2.5g)').replace('VN SN 0 DC 1.5 AC .5 180',f'VN SN 0 SIN(1.5 {amp} 2.5g 0 0 180)')
 d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ntran 2p 81n 0 2p\n'+f'wrdata /work/{name}.dat '+' '.join(probes)+'\n.endc\n.end\n'
 if RING:
  for line in (f'VP SP 0 SIN(1.5 {amp} 2.5g)\n',f'VN SN 0 SIN(1.5 {amp} 2.5g 0 0 180)\n','RP SP P 25\n','RN SN N 25\n'):
   assert d.count(line)==1;d=d.replace(line,'')
  add='.include /screen/pll/ring_vco_split.spice\nVPLL PLLVDD 0 3.3\nVCTRL CTRL 0 1.08\nVREGEN REGEN 0 1.08\nXVCO CTRL REGEN PLLVDD 0 P N pt_split_ring LOAD_L=5.25u CAP_W=4u CAP_L=3u\nCP P 0 25f\nCN N 0 25f\n'
  for stage,vp,vn in [(0,1.718,1.714),(1,1.714,1.718),(2,1.718,1.714)]:add+=f'.ic v(XVCO.N{stage}P)={vp} v(XVCO.N{stage}N)={vn}\n'
  d=d.replace('.control',add+'.control').replace('tran 2p 81n 0 2p\n','tran 2p 81n 0 2p uic\n')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as f:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,single_leg_peak_v=amp,returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
