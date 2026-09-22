"""Actual ring/RC/buffers driving two PDK mixers; ideal finite-impedance RF port."""
import hashlib,json,subprocess,sys
LNA="--lna" in sys.argv
FINAL="--final-stage" in sys.argv
assert not FINAL or LNA
ACCOUPLED="--ac-coupled" in sys.argv
assert not ACCOUPLED or (LNA and FINAL)
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());c=r['cases'][0];src=B/'a0.4.spice';assert sha(src)==c['artifacts_sha256']['.spice']
sources=[Path(p) for p in r['source_sha256_before']];assert {str(p):sha(p) for p in sources}==r['source_sha256_after'];sources.append(Path('/wifi/rf_switch_mixer/mixer.spice'))
if LNA:sources.append(Path('/wifi/rf_lna/lna_cs_core.spice'))
if FINAL:sources.append(Path('/screen/quadrature/lo_final_stage.spice'))
before={str(p):sha(p) for p in sources}
original=src.read_text();addition='''.include /wifi/rf_switch_mixer/mixer.spice
RRF RFS RF 300
XMI RF OIP OIN MIP MIN 0 wifi_rf_switch_mixer
XMQ RF OQP OQN MQP MQN 0 wifi_rf_switch_mixer
RMIP MIP 0 1k
RMIN MIN 0 1k
RMQP MQP 0 1k
RMQN MQN 0 1k
CMIP MIP 0 1p
CMIN MIN 0 1p
CMQP MQP 0 1p
CMQN MQN 0 1p
'''
extra='v(RF) v(MIP) v(MIN) v(MQP) v(MQN) i(VRF)'
if LNA:extra+=' v(LG) v(LS) v(LIN) i(VLNA) @m.xlna.x1.m0[vds] @m.xlna.x1.m0[vdsat] @m.xlna.x1.m0[id]'
if ACCOUPLED:extra+=' v(MRFIN)'
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),rf_hz=2.51542263e9,lna_mode=LNA,final_stage=FINAL,ac_coupled=ACCOUPLED,rf_bias_v=0 if LNA else 1.5,source_ohm=50 if LNA else 300,amplitudes_v=[0,.001] if LNA else [0,.01],horizon_ns=201,scope='Actual LNA and two mixers; prebiased gate, seeded ring; ideal supplies/bias/passives; no ADC/PLL' if LNA else 'Two actual mixers; matched zero/tone controls; ideal RF bias/source and baseband terminations, no LNA/ADC/PLL'),indent=2)+'\n')
rows=[]
for name,amp in [('zero',0),('tone',.001 if LNA else .01)]:
 d=original.replace('.control',addition+f'VRF RFS 0 SIN(1.5 {amp} 2.51542263g)\n.control').replace('tran 2p 81n 0 2p uic','tran 2p 201n 0 2p uic').replace('/work/a0.4.dat',f'/work/{name}.dat')
 d='\n'.join(line+' '+extra if line.startswith('wrdata ') else line for line in d.splitlines())+'\n'
 if LNA:
  lna='.include /wifi/rf_lna/lna_cs_core.spice\nVLNA LNAVDD 0 3.3\nVBIAS LBIAS 0 1.5\nRRF RFS LIN 50\nCCRF LIN LG 20p\nRB LG LBIAS 1meg\nRD LNAVDD RF 300\nRS LS 0 82\nXLNA LG RF LS 0 wifi_lna_cs_core\n.ic v(LG)=1.5\n'
  d=d.replace('RRF RFS RF 300\n',lna).replace(f'VRF RFS 0 SIN(1.5 {amp}',f'VRF RFS 0 SIN(0 {amp}')
  d=d.replace('tran 2p 201n 0 2p uic','save all @m.xlna.x1.m0[vds] @m.xlna.x1.m0[vdsat] @m.xlna.x1.m0[id]\ntran 2p 201n 0 2p uic')
 if FINAL:
  added='.include /screen/quadrature/lo_final_stage.spice\n'
  for node in ('IP','IN','QP','QN'):
   old=f'XB{node} B{node} O{node} VDD 0 pt_lo_buffer';assert d.count(old)==1
   d=d.replace(old,f'XB{node} B{node} PRE{node} VDD 0 pt_lo_buffer')
   added+=f'XF{node} PRE{node} O{node} VDD 0 pt_lo_final_stage\n'
  d=d.replace('.control',added+'.control')
 if ACCOUPLED:
  d=d.replace('XMI RF OIP','XMI MRFIN OIP').replace('XMQ RF OQP','XMQ MRFIN OQP').replace('.control','XAC RF MRFIN pt_ref_reservoir_256\n.control')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,amplitude_v=amp,returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
