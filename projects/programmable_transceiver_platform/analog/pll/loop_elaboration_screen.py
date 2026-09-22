"""Elaborate prepared autonomous deck; no operating-point or transient claim."""
import argparse,hashlib,json,re,subprocess
ap=argparse.ArgumentParser();ap.add_argument("--latest",action="store_true");args=ap.parse_args()
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());src=B/('latest.spice' if args.latest else 'closed.spice');assert sha(src)==m['deck_sha256' if args.latest else 'prepared_deck_sha256']
d=src.read_text();a=d.index('.control\n');b=d.index('.endc',a)
probe=d[:a]+'.control\nlisting expand\nquit\n'+d[b:]
p=O/'elaborate.spice';p.write_text(probe)
with (O/'elaborate.log').open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
log=(O/'elaborate.log').read_text();assert r.returncode==0
assert not re.search(r'(?im)^.*(?:error:|unknown subckt|could not find|fatal error)',log)
# Expanded listing must contain nested follower and steering-switch devices.
for token in ('xbuf.xin','xcp.xpd','xdc'):assert token in log.lower(),token
if args.latest:
 for token in ('xq.xrip','m.xmi.xp0.m0 rf oip mip 0','m.xmq.xp0.m0 rf oqp mqp 0','xd1','xfi','xfq'):assert token in log.lower(),token
out=dict(status='expanded_listing_only',returncode=r.returncode,prepared_deck_sha256=sha(src),artifacts_sha256={e:sha(O/('elaborate'+e)) for e in ('.spice','.log')},limitations=['No operating point, time evolution, lock, noise or stability test.','Dependencies were resolved by simulator; separate execution runner retains model hashes.'])
(O/'result.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
