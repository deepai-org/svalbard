#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-startup-state'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending terminal startup comparison');raise SystemExit(0)
r=json.loads((W/'result.json').read_text());assert [c['name'] for c in r['cases']]==['ideal_uic','ring_probe'];rows=[]
extra='v(CODE) v(BN) '+' '.join(f'v(D{i})' for i in range(8))+' v(XD.L0) v(XD.L0B) v(XD.H1) v(XD.H1B) v(XD.H15) v(XD.H15B) v(XD.XCL0.T) v(XD.XCH1.T)'
for c in r['cases']:
 name=c['name'];B=R/('scratch/transceiver-tx-buffered-lo' if name=='ideal_uic' else 'scratch/transceiver-tx-ring-driven');src=B/'nmos_c255.spice';m=json.loads((W/(name+'_manifest.json')).read_text());assert m['extra_vectors']==extra and sha(src)==m['baseline_deck_sha256'];assert c['source_sha256_before']==c['source_sha256_after']==m['source_sha256_before']
 d=(W/(name+'.spice')).read_text();restored=d.replace(' '+extra+'\n','\n').replace(f'/work/{name}.dat','/work/nmos_c255.dat')
 if name=='ideal_uic':restored=restored.replace('tran 2p 40n 0 2p uic','tran 2p 10n 0 2p')
 assert restored==src.read_text() and sha(W/(name+'.spice'))==m['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in (W/(name+'.log')).read_text().lower()
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=40e-9
 assert h[-len(extra.split()):]==extra.lower().split()
 row=dict(name=name,completed=True)
 if name=='ring_probe':
  old=np.loadtxt(B/'nmos_c255.dat',skiprows=1);assert np.array_equal(a[:,:old.shape[1]],old);row['original_vectors_bit_identical']=True
 a=a[a[:,0]>=30e-9];t=a[:,0]
 def v(k):return a[:,h.index(k)]
 row['late_node_ranges_v']={k:[float(v(k).min()),float(v(k).max())] for k in extra.lower().split()}
 row['rf_peak_to_peak_v']=float(np.ptp(v('v(rfp)')-v('v(rfn)')))
 row['dac_mean_differential_v']=float(np.trapezoid(v('v(op)')-v('v(on)'),t)/(t[-1]-t[0]));rows.append(row)
out=dict(status='completed_startup_state_diagnostic',cases=rows,provenance=r,limitations=['Ideal-clock replay changes UIC and duration, not a supply-ramp/cold-start qualification.', 'Ring replay is observation-only; exact numerical reproduction checked.', 'Selected logic nodes do not constitute complete decoder proof; no noise/modulation qualification.'])
(P/'evidence/tx-startup-state.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
