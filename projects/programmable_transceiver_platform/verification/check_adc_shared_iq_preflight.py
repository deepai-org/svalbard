#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-shared-iq-preflight';B=R/'scratch/transceiver-adc-sar8-reference-compensated'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());original=(B/'typical_first-1.spice').read_text();assert sha(B/'typical_first-1.spice')==m['baseline_deck_sha256'] and sha(B/'typical_first1.spice')==m['opposite_history_deck_sha256']
selected={'VIP','VIN','RIP','RIN','XS','XD','XC','XOP0','XOP1','XON0','XON1','CP','CN','XCTL','IBN','IBP','XBN','XBP','XBPDRV','XBNDRV','XTRACK'}|{f'XDRV{i}' for i in range(8)}
shared={'0','VDD','VLOG','VDRV','VBUF','VH','VL','RN','START','UPDATE','SC','SCB','CLK','MASKB'};assert set(m['shared_nodes'])==shared and {x['original'].split()[0] for x in m['channel_copy']}==selected
other=(B/'typical_first1.spice').read_text().splitlines();copies=[]
for x in m['channel_copy']:
 assert x['original'] in original.splitlines();old=x['source'].split();new=x['copy'].split();assert len(new)==len(old) and new[0]==old[0][0]+'Q_'+old[0][1:]
 assert x['source']==(next(l for l in other if l.startswith(old[0]+' ')) if old[0] in ('VIP','VIN') else x['original'])
 n=(next((i for i,f in enumerate(old) if '=' in f),len(old))-1) if old[0].startswith('X') else 3
 assert new[n:]==old[n:]
 for before,after in zip(old[1:n],new[1:n]):assert after==(before if before in shared else 'Q_'+before)
 copies.append(x['copy'])
vectors='v(Q_HP) v(Q_HN) v(Q_QP) v(Q_QN) v(Q_DONE) '+' '.join(f'v(Q_D{i})' for i in range(8))
expected=original.replace('.control','\n'.join(copies)+'\n.control').replace('tran 5p 209.9n 0 5p','tran 5p 1n 0 5p').replace('/work/typical_first-1.dat','/work/preflight.dat').replace('\n.endc',' '+vectors+'\n.endc');assert (W/'preflight.spice').read_text()==expected and sha(W/'preflight.spice')==m['deck_sha256_before']
out=dict(status='pending',verified_added_top_level_elements=len(copies),single_reference_pair_retained=True)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('preflight'+ext))==h
 assert r['returncode']==0 and 'aborted' not in (W/'preflight.log').read_text().lower()
 with (W/'preflight.dat').open() as f:h=f.readline().lower().split()
 assert h==['time']+next(l for l in expected.splitlines() if l.startswith('wrdata ')).lower().split()[2:]
 a=np.loadtxt(W/'preflight.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=1e-9
 out.update(status='completed_1ns_elaboration_only',provenance=r,actual_stop_ns=float(a[-1,0]*1e9))
out['limitations']=['No sample conversion occurs in1ns; no shared-reference accuracy or dynamic power claim.', 'Ideal shared supplies and phase clocks, selected opposite inputs; actual driver/load coupling through reference pair only.', 'Complete conversion and multiple channel relationships remain to be tested.']
(P/'evidence/adc-shared-iq-preflight.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
