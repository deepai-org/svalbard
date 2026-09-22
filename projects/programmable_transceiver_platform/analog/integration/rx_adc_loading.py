"""Matched real loading versus ideal isolation; latter is a diagnostic control."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');args=ap.parse_args()
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
assert r['sources_before']==r['sources_after']
for ext,h in r['artifacts_sha256'].items():assert sha(B/('connected'+ext))==h
before={}
for name,h in r['sources_before'].items():
 # Parent preparation is mounted separately; other dependencies retain their paths.
 p=Path('/prepared/connected.spice') if name=='/baseline/connected.spice' else Path(name)
 assert sha(p)==h,str(p);before[str(p)]=h
before[str(Path(__file__))]=sha(Path(__file__))
base=(B/'connected.spice').read_text();horizon=1 if args.preflight else 610
extra=[f'v(XRX.{n})' for n in ('P','N','MIP','MIN','MQP','MQN','LG','LS')]
extra += [f'v(XADC.{n})' for n in ('XBPDRV.T','XBNDRV.T','XQ_BPDRV.T','XQ_BNDRV.T')]
wr=next(l for l in base.splitlines() if l.startswith('wrdata '))
control='XADC FIP FIN FQP FQN pt_adc_pair_loaded'
isolated='''EISOIP AIP 0 FIP 0 1
EISOIN AIN 0 FIN 0 1
EISOQP AQP 0 FQP 0 1
EISOQN AQN 0 FQN 0 1
XADC AIP AIN AQP AQN pt_adc_pair_loaded'''
assert base.count(control)==1
for case in ('loaded','isolated'):
 out=O/case;out.mkdir(exist_ok=False)
 newwr=wr.replace('/work/connected.dat',f'/work/{case}/connected.dat')+' '+' '.join(extra)
 deck=base.replace('tran 2p 1n 0 2p uic',f'tran 2p {horizon}n 0 2p uic').replace(wr,newwr)
 if case=='isolated':deck=deck.replace(control,isolated)
 back=deck.replace(isolated,control) if case=='isolated' else deck
 assert back.replace(f'tran 2p {horizon}n 0 2p uic','tran 2p 1n 0 2p uic').replace(newwr,wr)==base
 p=out/'connected.spice';p.write_text(deck)
 m=dict(case=case,parent_sha256=sha(B/'connected.spice'),deck_sha256=sha(p),sources_before=before,requested_horizon_ns=horizon,extra_probes=extra,control_scope='Isolated case inserts ideal unity VCVS inputs solely to remove back-loading; ADC and clock events retained. Not a proposed hardware buffer.')
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 start=time.monotonic()
 with (out/'connected.log').open('w') as log:
  try:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=180 if args.preflight else 10800);code=q.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==m['deck_sha256']
 result=dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={e:sha(out/('connected'+e)) for e in ('.spice','.log','.dat') if (out/('connected'+e)).exists()})
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(case,code,timeout,flush=True)
