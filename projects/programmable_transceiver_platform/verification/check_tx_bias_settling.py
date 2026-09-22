#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-bias-settling';B=R/'scratch/transceiver-tx-startup-state'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending terminal bias settling result');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert m['source_sha256_before']==r['source_sha256_before']==r['source_sha256_after'];src=B/'ideal_uic.spice';assert sha(src)==m['baseline_deck_sha256'];assert [c['name'] for c in r['cases']]==['op','uic'];data={}
for c in r['cases']:
 name=c['name'];uic=' uic' if name=='uic' else ''
 expected=src.read_text().replace('VLO LOIN 0 PULSE(0 3.3 1n 20p 20p 180p 400p)','VLO LOIN 0 3.3').replace('VLOB LOBIN 0 PULSE(3.3 0 1n 20p 20p 180p 400p)','VLOB LOBIN 0 0').replace('tran 2p 40n 0 2p uic',f'tran 20p 1u 0 20p{uic}').replace('/work/ideal_uic.dat',f'/work/{name}.dat')
 assert (W/(name+'.spice')).read_text()==expected and sha(W/(name+'.spice'))==c['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in (W/(name+'.log')).read_text().lower()
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 assert h==['time']+next(l for l in expected.splitlines() if l.startswith('save ')).lower().split()[1:]
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=1e-6;data[name]=(h,a)
h,a=data['uic'];ho,ao=data['op'];assert h==ho
metrics={}
for label,y,ref in [('bias_v',a[:,h.index('v(bn)')],ao[-1,h.index('v(bn)')]),('dac_differential_v',a[:,h.index('v(op)')]-a[:,h.index('v(on)')],ao[-1,h.index('v(op)')]-ao[-1,h.index('v(on)')])]:
 error=abs(y-ref);outside=np.where(error>1e-3)[0];last=int(outside[-1]) if len(outside) else None
 metrics[label]=dict(op_reference_v=float(ref),final_uic_v=float(y[-1]),final_error_v=float(error[-1]),last_outside_1mv_ns=float(a[last,0]*1e9) if last is not None else None,remains_within_1mv_after_ns=float(a[last+1,0]*1e9) if last is not None and last+1<len(a) else (float(a[0,0]*1e9) if last is None else None))
out=dict(status='completed_static_bias_startup_diagnostic',metrics=metrics,provenance=r,limitations=['1mV is a diagnostic settling band, not an allocated startup/accuracy specification.', 'Static LO removes periodic loading; connected GHz startup can differ.', 'Ideal20uA bias and step supplies; actual bias generator and supply ramp remain absent.', 'No cold oscillator startup, modulation/noise or process/mismatch qualification.'])
(P/'evidence/tx-bias-settling.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(metrics,indent=2))
