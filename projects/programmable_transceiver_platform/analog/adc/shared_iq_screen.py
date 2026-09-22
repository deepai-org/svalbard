"""Add a second physical ADC channel to the existing compensated reference fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
src=B/'typical_first-1.spice';opposite=B/'typical_first1.spice'
for p in (src,opposite):assert sha(p)==next(c for c in base['cases'] if c['name']==p.stem)['artifacts_sha256']['.spice']
selected={'VIP','VIN','RIP','RIN','XS','XD','XC','XOP0','XOP1','XON0','XON1','CP','CN','XCTL','IBN','IBP','XBN','XBP','XBPDRV','XBNDRV','XTRACK'}|{f'XDRV{i}' for i in range(8)}
shared={'0','VDD','VLOG','VDRV','VBUF','VH','VL','RN','START','UPDATE','SC','SCB','CLK','MASKB'}
original=src.read_text();other={l.split()[0]:l for l in opposite.read_text().splitlines() if l and not l.startswith(('*','.'))};added=[];mapping=[]
for line in original.split('.control')[0].splitlines():
 fields=line.split()
 if not fields or fields[0] not in selected:continue
 old=line
 if fields[0] in ('VIP','VIN'):line=other[fields[0]];fields=line.split()
 name=fields[0];fields[0]=name[0]+'Q_'+name[1:]
 if name.startswith('X'):
  model_index=next((i for i,f in enumerate(fields) if '=' in f),len(fields))-1
  indices=range(1,model_index)
 else:indices=range(1,3)
 for i in indices:
  if fields[i] not in shared:fields[i]='Q_'+fields[i]
 new=' '.join(fields);added.append(new);mapping.append(dict(original=old,source=line,copy=new))
assert len(added)==len(selected)==29
vectors='v(Q_HP) v(Q_HN) v(Q_QP) v(Q_QN) v(Q_DONE) '+' '.join(f'v(Q_D{i})' for i in range(8))
d=original.replace('.control','\n'.join(added)+'\n.control').replace('tran 5p 209.9n 0 5p','tran 5p 1n 0 5p').replace('/work/typical_first-1.dat','/work/preflight.dat').replace('\n.endc',' '+vectors+'\n.endc')
p=O/'preflight.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),opposite_history_deck_sha256=sha(opposite),deck_sha256_before=pre,channel_copy=mapping,shared_nodes=sorted(shared),scope='Second actual ADC, opposite input history, common ideal clocks/supplies; one actual compensated reference pair and unchanged reservoirs.1ns elaboration only.'),indent=2)+'\n')
with (O/'preflight.log').open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180)
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=r.returncode,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('preflight'+ext)) for ext in ('.spice','.log','.dat') if (O/('preflight'+ext)).exists()}),indent=2)+'\n');print(r.returncode)
