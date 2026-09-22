"""Replace finite ideal dummy source by existing FET follower; seeded reservoir."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());c=next(c for c in r['cases'] if c['name']=='reservoir');assert c['returncode']==0 and not c['timed_out']
src=B/'reservoir.spice';assert sha(src)==c['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
for p in (Path('/screen/reference/buffer_scaled.spice'),Path(__file__)):before[str(p)]=sha(p)
old='VDUMMY DDRIVE 0 1.08\nRDUMMY DDRIVE DUMMY 1k'
new='''.include /screen/reference/buffer_scaled.spice
VDRV VDRV 0 3.3
IBDN VDRV BDN 20u
IBDP BDP 0 20u
XBDN BDN BDN 0 0 nfet_03v3 w=8u l=.5u
XBDP BDP BDP VDRV VDRV pfet_03v3 w=8u l=.5u
XBUF CTRL DDRIVE BDN BDP VDRV 0 pt_reference_buffer_scaled S=0.0625
VDUMMY DUMMY DDRIVE 0'''
base=src.read_text();assert base.count(old)==1
d=base.replace(old,new).replace('/work/reservoir.dat','/work/follower.dat')
extra=' i(VDRV) v(BDN) v(BDP) v(XBUF.X) v(XBUF.T)'
d='\n'.join(line+extra if line.startswith(('save ','wrdata ')) else line for line in d.split('\n'))
p=O/'follower.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),replacement_old=old,replacement_new=new,extra_probes=extra,limitations=['Ideal clocks, output clamp,3.3V supplies and20uA bias currents remain.','Reservoir starts precharged1.08V; not whole-chip cold startup.','Follower fractional multiplicity requires physical normalization and recheck.']),indent=2)+'\n')
with (O/'follower.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=360);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
assert sha(p)==h
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('follower'+e)) for e in ('.spice','.log','.dat') if (O/('follower'+e)).exists()}),indent=2)+'\n')
print(code,timeout,flush=True)
