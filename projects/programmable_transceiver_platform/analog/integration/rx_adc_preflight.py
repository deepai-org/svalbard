"""Short elaboration of the actual connected receiver and dual ADC."""
import argparse,hashlib,json,re,subprocess,time
ap=argparse.ArgumentParser();ap.add_argument("--dedup",action="store_true");args=ap.parse_args()
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'connected.spice')==m['deck_sha256']
before={}
def scan(p):
 p=p.resolve()
 if str(p) in before:return
 before[str(p)]=sha(p)
 for line in p.read_text().splitlines():
  match=re.match(r'\s*\.(?:include|inc|lib)\s+["\']?([^\s"\']+)',line,re.I)
  if not match:continue
  name=match.group(1)
  # A library section declaration is not a file dependency.
  if not (name.startswith('/') or '.' in name):continue
  child=Path(name);child=child if child.is_absolute() else p.parent/child
  assert child.is_file(),str(child)
  scan(child)
scan(B/'connected.spice');before[str(Path(__file__).resolve())]=sha(Path(__file__))
base=(B/'connected.spice').read_text();assert base.count('tran 2p 610n 0 2p uic')==1
probes=[f'v(XADC.{n})' for n in ['BN','BP','Q_BN','Q_BP','RBN','RBP','SC','SCB','CLK','MASKB','DONE','Q_DONE']]
probes += [f'v(XADC.{prefix}D{i})' for prefix in ('','Q_') for i in range(8)]
wr=next(l for l in base.splitlines() if l.startswith('wrdata '));newwr=wr+' '+' '.join(probes)
deck=base.replace('tran 2p 610n 0 2p uic','tran 2p 1n 0 2p uic').replace(wr,newwr)
assert deck.replace('tran 2p 1n 0 2p uic','tran 2p 610n 0 2p uic').replace(newwr,wr)==base
removed_include='.include /screen/reference/reservoir_mim.spice\n'
if args.dedup:
 assert deck.count(removed_include)==1
 assert removed_include.strip() in Path('/screen/quadrature/rc_split.spice').read_text().splitlines()
 deck=deck.replace(removed_include,'')
p=O/'connected.spice';p.write_text(deck)
(O/'manifest.json').write_text(json.dumps(dict(parent_sha256=m['deck_sha256'],deck_sha256=sha(p),sources_before=before,extra_probes=probes,requested_horizon_ns=1,deduplicated=args.dedup),indent=2)+'\n')
start=time.monotonic()
with (O/'connected.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=180);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={name:sha(Path(name)) for name in before};assert before==after
out=dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,sources_before=before,sources_after=after,artifacts_sha256={ext:sha(O/('connected'+ext)) for ext in ('.spice','.log','.dat') if (O/('connected'+ext)).exists()})
(O/'result.json').write_text(json.dumps(out,indent=2)+'\n');print(code,timeout)
