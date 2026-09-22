"""Prepare actual receiver driven by saved autonomous ring outputs; reproduction unproven."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-latest-rf-loop-selective';O=R/'scratch/transceiver-lo-receiver-replay-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=json.loads((P/'evidence/latest-rf-loop-selective.json').read_text());assert e['completed'];assert sha(B/'latest.spice')==e['provenance']['artifacts_sha256']['.spice']
names=['v(p)','v(n)','v(bip)','v(bin)','v(bqp)','v(bqn)','v(lg)','v(ls)','v(fip)','v(fin)','v(fqp)','v(fqn)','v(oip)','v(oin)','v(oqp)','v(oqn)'];rows=[];digest=hashlib.sha256()
with (B/'latest.dat').open('rb') as f:
 head=f.readline();digest.update(head);header=head.decode().lower().split();cols=[0]+[header.index(n) for n in names]
 for line in f:
  digest.update(line);time=float(line.split(None,1)[0])
  if 6911.99e-9<=time<=7936.01e-9:
   w=line.split();rows.append([float(w[k]) for k in cols])
assert digest.hexdigest()==e['provenance']['artifacts_sha256']['.dat'];a=np.array(rows);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
lo,hi=6912e-9,7936e-9;t=np.r_[lo,a[(a[:,0]>lo)&(a[:,0]<hi),0],hi];values=np.column_stack([np.interp(t,a[:,0],a[:,i]) for i in range(1,len(names)+1)])
parent=(B/'latest.spice').read_text();body=parent.split('.include /vco/divider.spice')[0];removed=[]
for l in body.splitlines():
 if l.startswith('XVCO ') or l.startswith('.ic v(XVCO.') or l.startswith('.ic v(LG)'):
  removed.append(l);body=body.replace(l+'\n','')
assert len(removed)==5 and 'XVCO CTRL' not in body
O.mkdir();stim=O/'ring_pwl.spice'
with stim.open('w') as f:
 for col,node in enumerate(('P','N')):
  f.write('VREPLAY'+node+' '+node+' 0 PWL(\n')
  for ti,vi in zip(t-lo,values[:,col]):f.write(f'+ {ti:.16e} {vi:.16e}\n')
  f.write('+ )\n')
seeds='\n'.join('.ic '+n+'='+format(values[0,k],'.16e') for k,n in enumerate(names) if n not in ('v(p)','v(n)'))
vectors=' '.join(names+[f'v(XB{x}.MID)' for x in ('IP','IN','QP','QN')]+['v(PREIP)','v(PREIN)','v(PREQP)','v(PREQN)'])
deck=body+'.include /prepared/ring_pwl.spice\n'+seeds+f'''
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save {vectors}
tran 2p 1024n 0 2p uic
wrdata /work/replay.dat {vectors}
.endc
.end
'''
(O/'replay.spice').write_text(deck);np.save(O/'parent_samples.npy',np.column_stack((t-lo,values)))
(O/'manifest.json').write_text(json.dumps(dict(parent_deck_sha256=sha(B/'latest.spice'),parent_waveform_sha256=digest.hexdigest(),source_provenance=e['provenance']['source_sha256_after'],removed_lines=removed,original_window_ns=[6912,7936],comparison_window_ns=[512,1024],sample_columns=['time']+names,artifacts_sha256={n:sha(O/n) for n in ('ring_pwl.spice','replay.spice','parent_samples.npy')},limitations=['Ideal P/N replay removes bidirectional loading and autonomous feedback; reproduction must be measured before tuning.','Only saved receiver node voltages seeded; unsaved internal state is not reconstructed.','Native piecewise-linear export plus interpolated endpoints; source breakpoint effects may change numerical behavior.']),indent=2)+'\n');print('Prepared',len(t),'P/N points; reproduction not yet tested')
